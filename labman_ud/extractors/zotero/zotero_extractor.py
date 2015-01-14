
from django.conf import settings
from django.db.models import Max
from django.template.defaultfilters import slugify

from entities.events.models import Event
from entities.persons.models import Person, Nickname
from entities.projects.models import Project, RelatedPublication
from entities.publications.models import *
from entities.utils.models import Tag, City, Country
from extractors.zotero.models import ZoteroExtractorLog
from labman_setup.models import ZoteroConfiguration


from datetime import datetime
from dateutil import parser
from pyzotero import zotero

import os
import pprint
import re


pp = pprint.PrettyPrinter(indent=4)

JCR_PATTERN = r'(jcr|if)(-*)(\d(\.|\,)\d+)'


####################################################################################################
# def: get_zotero_variables()
####################################################################################################

def get_zotero_variables():
    try:
        zotero_config = ZoteroConfiguration.objects.get()

        api_key = zotero_config.api_key
        library_id = zotero_config.library_id
        library_type = zotero_config.library_type

        return base_url, api_key, library_id, library_type

    except:
        print "ZoteroConfiguration object not configured in admin panel"

        return '', '', '', ''
        

####################################################################################################
# def: get_zotero_connection()
####################################################################################################        
def get_zotero_connection():
    api_key, library_id, library_type = get_zotero_variables()
    zot = zotero.Zotero(library_id = library_id, library_type=library_type, api_key=api_key)
    
    return zot


####################################################################################################
# def: get_last_zotero_version()
####################################################################################################

def get_last_zotero_version():
    zot = get_zotero_connection()

    items = zot.items(limit=1)
    if len(items):
        latest_version_number = items[0]['version']
    else:
        latest_version_number = 0

    return latest_version_number


####################################################################################################
# def: get_last_synchronized_zotero_version()
####################################################################################################

def get_last_synchronized_zotero_version():
    try:
        last_version = ZoteroExtractorLog.objects.all().aggregate(Max('version'))['version__max']
        if last_version is None:
            last_version = 0

    except:
        last_version = 0

    return last_version


####################################################################################################
# def: get_item_keys_since_last_synchronized_version()
####################################################################################################

def extract_publications_from_zotero(from_version):
    last_zotero_version = get_last_zotero_version()

    if from_version == last_zotero_version:
        print 'Labman is updated to the last version in Zotero (%d)' % (last_zotero_version)

        return []

    else:
        if from_version > last_zotero_version:
            # This should never happen, but just in case, we solve the error by syncing the penultimate version in Zotero
            from_version = last_zotero_version - 1
            print 'Error solved'

        print 'Getting items since version %d' % (from_version)
        print 'Last version in Zotero is %d' % (last_zotero_version)

        zot = get_zotero_connection()

        items = zot.items(since=last_zotero_version)

        print
        print '*' * 50
        print '%d new items' % len(items)
        print '*' * 50
        print
        
        items_ordered = {}
        attachments = []
        for item in items:
            if item['data']['itemType'] == 'attachment':
                attachments.append(item)
            else:
                item_id = item['key']
                items_ordered[item_id] = item
                
        for a in attachments:
            parent_id = a['data']['parentItem']
            if items_ordered.has_key(parent_id):
                items_ordered[parent_id]['attachment'] = a
            else: 
                #only the attachment has been modified
                parent_publication = zot.item(parent_id)
                publication_slug = slugify(parent_publication['data']['title'])
                _save_attachement(a['key'], publication_slug, a['filename'])
         
        
        for i_id in items_ordered:
            generate_publication(items_ordered[i_id])


####################################################################################################
# def: clean_database()
####################################################################################################

def clean_database():
    Publication.objects.all().delete()

    PublicationAuthor.objects.all().delete()
    PublicationEditor.objects.all().delete()
    PublicationTag.objects.all().delete()

    ZoteroExtractorLog.objects.all().delete()

    # TODO check this
    # Are academic events only created by publications?
    # Event.objects.filter(event_type='Academic event').delete()
    
    # TODO check this, events also has cities
    # It's really necesary to delete the unused cities?
    # City.objects.all().delete()

####################################################################################################
# def: generate_publication_from_zotero()
####################################################################################################

def generate_publication(item):
    publication_type = item['data']['itemType']

    print '\t[%s] > %s' % (publication_type.encode('utf-8'), item['data']['title'].encode('utf-8'))

    if publication_type == 'conferencePaper':
        parse_conference_paper(item)
    elif publication_type == 'bookSection':
        parse_book_section(itemy)
    elif publication_type == 'book':
        parse_authored_book(item)
    elif publication_type == 'journalArticle':
        parse_journal_article(item)
    elif publication_type == 'magazineArticle':
        parse_magazine_article(item)
    elif publication_type == 'attachment':
        pass # this should not happen
    elif publication_type == 'thesis':
        parse_thesis(item)
    else:
        print
        print '*' * 50
        print 'NOT PARSED:\t\tPublication type: %s' % publication_type
        print '*' * 50
        print
        pp.pprint(content_json)
        print
        
###############################################################################
###############################################################################
# Item parsing
###############################################################################
###############################################################################
        
####################################################################################################
# def: parse_journal_article()
####################################################################################################

def parse_journal_article(item):
    publication_slug = slugify(item['data']['title'])
    try:
        journal_article = JournalArticle.objects.get(slug=publication_slug)

    except:
        journal_article = JournalArticle()

        journal_article.title = item['data']['title']
        journal_article.short_title = _extract_short_title(item)

        journal_article.abstract = _assign_if_exists(item, 'abstractNote')
        journal_article.pages = _assign_if_exists(item, 'pages')
        journal_article.doi = _extract_doi(item)

        journal_article.parent_journal = parse_journal(item)

        journal_article.published = _parse_date(item['data']['date'])
        journal_article.year = journal_article.published.year

        journal_article.bibtex = _extract_bibtex(item['key'])

        journal_article.save()

    _save_publication_authors(_extract_authors(item), journal_article)

    _extract_tags(item, journal_article)
    
    if item.has_key('attachment'):         
         _save_attachement(item['attachment']['key'], publication_slug, item['attachment']['filename'])

    _save_zotero_extractor_log(item, journal_article)     
    
    
####################################################################################################
# def: parse_journal()
####################################################################################################

def parse_journal(item):
    try:
        journal = Journal.objects.get(
            slug=slugify(item['data']['publicationTitle']),
            issue=item['data']['issue'],
            volume=item['data']['volume']
        )
        
    except:
        journal = Journal()

        journal.title = item['data']['publicationTitle']

        journal.issn = _assign_if_exists(item, 'ISSN')
        journal.volume = _assign_if_exists(item, 'volume')
        journal.series = _assign_if_exists(item, 'series')
        journal.publisher = _assign_if_exists(item, 'publisher')
        journal.place = _assign_if_exists(item, 'place')
        journal.journal_abbreviation = _assign_if_exists(item, 'journalAbbrevation')
        journal.issue = _assign_if_exists(item, 'issue')

        journal.published = _parse_date(item['data']['date'])
        journal.year = journal.published.year

        journal.save()

    return journal
    
####################################################################################################
# def: parse_conference_paper()
####################################################################################################

def parse_conference_paper(item):
    publication_slug = slugify(item['data']['title'])
    try:
        conference_paper = ConferencePaper.objects.get(slug=publication_slug)

    except:
        conference_paper = ConferencePaper()

        conference_paper.title = item['data']['title']
        conference_paper.short_title = _extract_short_title(item)

        conference_paper.abstract = _assign_if_exists(item, 'abstractNote')
        conference_paper.pages = _assign_if_exists(item, 'pages')
        conference_paper.doi = _extract_doi(item)

        conference_paper.parent_proceedings = parse_proceedings(item)
        conference_paper.presented_at = parse_conference(item, conference_paper.parent_proceedings)

        conference_paper.published = _parse_date(item['data']['date'])
        conference_paper.year = conference_paper.published.year

        conference_paper.bibtex = _extract_bibtex(item['key'])

        conference_paper.save()

    _save_publication_authors(_extract_authors(item), conference_paper)

    _extract_tags(item, conference_paper)
    
    if item.has_key('attachment'):         
         _save_attachement(item['attachment']['key'], publication_slug, item['attachment']['filename'])

    _save_zotero_extractor_log(item, conference_paper)


####################################################################################################
# def: parse_proceedings()
####################################################################################################

def parse_proceedings(item):
    if item['data']['proceedingsTitle'] != '':
        proceedings_title = item['data']['proceedingsTitle']

    else:
        if item['data']['conferenceName'] != '':
            proceedings_title = 'Proceedings of conference: %s' % item['data']['conferenceName']

        else:
            proceedings_title = 'Proceedings for article: %s' % item['data']['title']

    try:
        proceedings = Proceedings.objects.get(
            slug=slugify(proceedings_title),
            date=item['data']['date']
        )

    except:
        proceedings = Proceedings()

        proceedings.title = proceedings_title

        proceedings.isbn = _assign_if_exists(item, 'ISBN')
        proceedings.volume = _assign_if_exists(item, 'volume')
        proceedings.series = _assign_if_exists(item, 'series')
        proceedings.publisher = _assign_if_exists(item, 'publisher')
        proceedings.place = _assign_if_exists(item, 'place')

        proceedings.published = _parse_date(item['data']['date'])
        proceedings.year = proceedings.published.year

        proceedings.save()

    return proceedings
    
####################################################################################################
# def: parse_conference()
####################################################################################################

def parse_conference(item, proceedings):
    if item['data'].has_key('conferenceName') and item['data']['conferenceName'] != '':
        try:
            event = Event.objects.get(
                slug=slugify(item['data']['conferenceName']),
                date=item['data']['date']
            )

        except:
            event = Event()

        event.event_type = 'Academic event'

        event.full_name = item['data']['conferenceName']

        if  item['data'].has_key('place') and item['data']['place'] != '':
            places_list = item['data']['place'].split(', ')

            if len(places_list) == 2:
                city_name = places_list[0]
                country_name = places_list[1]

                event_location = ''

                if city_name and city_name != '':
                    try:
                        city = City.objects.get(slug=slugify(city_name))

                    except:
                        city = City(
                            full_name=city_name,
                        )

                        city.save()

                    event_location = city_name

                else:
                    city = None

                if country_name and country_name != '':
                    try:
                        country = Country.objects.get(slug=slugify(country_name))

                    except:
                        country = Country(
                            full_name=country_name,
                        )

                        country.save()

                    city.country = country
                    city.save()

                    if city_name and city_name != '':
                        event_location = '%s (%s)' % (event_location, country_name)
                    else:
                        event_location = '(%s)' % country_name

                else:
                    country = None

                event.host_city = city
                event.host_country = country

                event.location = event_location

        event.published = _parse_date(item['data']['date'])
        event.year = event.published.year

        event.proceedings = proceedings

        event.save()

        return event

    else:
        return None
        
####################################################################################################
# def: parse_book_section()
####################################################################################################

def parse_book_section(item):
    publication_slug = slugify(item['data']['title'])
    try:
        book_section = BookSection.objects.get(slug=publication_slug)

    except:
        book_section = BookSection()

        book_section.title = item['data']['title']
        book_section.short_title = _extract_short_title(item)

        book_section.abstract = _assign_if_exists(item, 'abstractNote')
        book_section.pages = _assign_if_exists(item, 'pages')
        book_section.doi = _extract_doi(item)

        book_section.parent_book = parse_book(item)

        book_section.published = _parse_date(item['data']['date'])
        book_section.year = book_section.published.year

        book_section.bibtex = _extract_bibtex(item['key'])

        book_section.save()

    _save_publication_authors(_extract_authors(item), book_section)

    _extract_tags(item, book_section)
    
    if item.has_key('attachment'):         
         _save_attachement(item['attachment']['key'], publication_slug, item['attachment']['filename'])

    _save_zotero_extractor_log(item, book_section)


####################################################################################################
# def: parse_book()
####################################################################################################

def parse_book(item):
    try:
        book = Book.objects.get(
            slug=slugify(item['data']['bookTitle']),
            date=item['data']['date']
        )

    except:
        book = Book()

        book.title = item['data']['bookTitle']

        book.isbn = _assign_if_exists(item, 'ISBN')
        book.volume = _assign_if_exists(item, 'volume')
        book.series = _assign_if_exists(item, 'series')
        book.publisher = _assign_if_exists(item, 'publisher')
        book.place = _assign_if_exists(item, 'place')

        book.published = _parse_date(item['data']['date'])
        book.year = book.published.year

        book.save()

    _save_publication_editors(_extract_editors(item), book)

    return book
    
####################################################################################################
# def: parse_authored_book()
####################################################################################################

def parse_authored_book(item):
    publication_slug = slugify(item['data']['title'])
    try:
        book = Book.objects.get(
            slug=publication_slug,
            date=item['data']['date']
        )

    except:
        book = Book()

        book.title = item['data']['title']
        book.short_title = _extract_short_title(item)

        book.abstract = _assign_if_exists(item, 'abstractNote')
        book.number_of_pages = _assign_if_exists(item, 'numPages')
        book.edition = _assign_if_exists(item, 'edition')
        book.doi = _extract_doi(item)

        book.isbn = _assign_if_exists(item, 'ISBN')
        book.volume = _assign_if_exists(item, 'volume')
        book.number_of_volumes = _assign_if_exists(item, 'numberOfVolumes')
        book.series = _assign_if_exists(item, 'series')
        book.series_number = _assign_if_exists(item, 'seriesNumber')
        book.publisher = _assign_if_exists(item, 'publisher')
        book.place = _assign_if_exists(item, 'place')

        book.published = _parse_date(item['data']['date'])
        book.year = book.published.year

        book.bibtex = _extract_bibtex(item['key'])

        book.save()

    _save_publication_authors(_extract_authors(item), book)

    _extract_tags(item, book)
    
    if item.has_key('attachment'):         
         _save_attachement(item['attachment']['key'], publication_slug, item['attachment']['filename'])

    _save_zotero_extractor_log(item, book)
    
####################################################################################################
# def: parse_magazine_article()
####################################################################################################

def parse_magazine_article(item):
    publication_slug = slugify(item['data']['title'])
    try:
        magazine_article = MagazineArticle.objects.get(slug=publication_slug)

    except:
        magazine_article = MagazineArticle()

        magazine_article.title = item['data']['title']
        magazine_article.short_title = _extract_short_title(item)

        magazine_article.abstract = _assign_if_exists(item, 'abstractNote')
        magazine_article.pages = _assign_if_exists(item, 'pages')
        magazine_article.doi = _extract_doi(item)

        magazine_article.parent_magazine = parse_magazine(item)

        magazine_article.published = _parse_date(item['data']['date'])
        magazine_article.year = magazine_article.published.year

        magazine_article.bibtex = _extract_bibtex(item['key'])

        magazine_article.save()

    _save_publication_authors(_extract_authors(item), magazine_article)

    _extract_tags(item, magazine_article)
    
    if item.has_key('attachment'):         
         _save_attachement(item['attachment']['key'], publication_slug, item['attachment']['filename'])

    _save_zotero_extractor_log(item, magazine_article)


####################################################################################################
# def: parse_magazine()
####################################################################################################

def parse_magazine(item):
    try:
        magazine = Magazine.objects.get(
            slug=slugify(item['data']['publicationTitle']),
            date=item['data']['date']
        )

    except:
        magazine = Magazine()

        magazine.title = item['data']['publicationTitle']

        magazine.issn = _assign_if_exists(item, 'ISSN')
        magazine.volume = _assign_if_exists(item, 'volume')
        magazine.issue = _assign_if_exists(item, 'issue')

        magazine.published = _parse_date(item['data']['date'])
        magazine.year = magazine.published.year

        magazine.save()

    return magazine





####################################################################################################
# def: parse_thesis()
####################################################################################################

def parse_thesis(item):
    author = _extract_authors(item)[0]

    try:
        Thesis.objects.get(slug=slugify(item['data']['title']))

    except:
        print
        print '*' * 75
        print '%s should register his/her thesis using labman\'s admin page' % author
        print '*' * 75
        print

###############################################################################
###############################################################################
# Common methods
###############################################################################
###############################################################################
        
####################################################################################################
# def: _extract_short_title()
####################################################################################################

def _extract_short_title(item):
    if item['data'].has_key('shortTitle') and item['shortTitle'] != '':
        return item['data']['shortTitle']

    else:
        index = item['data']['title'].find(':')

        if index != -1:
            return item['data']['title'][:index]        
        
####################################################################################################
# def: _assign_if_exists()
####################################################################################################

def _assign_if_exists(item, key):
    if item['data'].has_key(key):
        if item['data'][key] != '':
            return item['data'][key]
            
####################################################################################################
# def: _extract_doi()
####################################################################################################

def _extract_doi(item):
    DOI_ORG_BASE_URL = 'http://dx.doi.org/'

    if item['data'].has_key('DOI'):
        if item['data']['DOI'] != '':
            return item['data']['DOI']

    elif item['data'].has_key('url'):
        if item['data']['url'] != '' and DOI_ORG_BASE_URL in item['data']['url']:
            base_url_end_index = len(DOI_ORG_BASE_URL)
            underscore_index = item['data']['url'].find('_') if item['data']['url'].find('_') != -1 else len(item['data']['url'])

            return item['data']['url'][base_url_end_index:underscore_index]
        
####################################################################################################
# def: _parse_date()
####################################################################################################

def _parse_date(date_string): 
    return parser.parse(date_string, fuzzy=True, default=datetime.now())   

####################################################################################################
# def: _extract_bibtex()
####################################################################################################

def _extract_bibtex(item_key):
    zot = get_zotero_connection()
    
    item = zot.item(item_key, format='bibtex')
    return item
    
####################################################################################################
# def: _extract_authors()
####################################################################################################

def _extract_authors(item):
    authors = []

    if  item['data'].has_key('creators') and len(item['data']['creators']) > 0:
        for creator_item in item['data']['creators']:
            creator_type = creator_item['creatorType']

            if creator_type == 'author':
                if 'name' in creator_item and creator_item['name'] != '':
                    author_name = str(creator_item['name'].encode('utf-8'))
                    author_first_surname = author_name.split(' ')[-1]
                    author_first_name = author_name.replace(' ' + author_first_surname, '')

                else:
                    author_first_name = creator_item['firstName'].encode('utf-8')
                    author_first_surname = creator_item['lastName'].encode('utf-8')

                author_slug = slugify('%s %s' % (author_first_name, author_first_surname))

                try:
                    # Check if author is in DB (comparing by slug)
                    author = Person.objects.get(slug=author_slug)

                except:
                    # If it isn't
                    try:
                        # Check if author name correspond with any of the posible nicknames of the authors in DB
                        nick = Nickname.objects.get(slug=author_slug)
                        author = nick.person
                    except:
                        # If there is no reference to that person in the DB, create a new one
                        author = Person(
                            first_name=author_first_name,
                            first_surname=author_first_surname
                        )

                        author.save()

                authors.append(author)

    return authors
    
####################################################################################################
# def: _save_publication_authors()
####################################################################################################

def _save_publication_authors(authors, publication):
    order = 1

    for author in authors:
        publication_author = PublicationAuthor(
            author=author,
            publication=publication,
            position=order,
        )

        publication_author.save()

        order += 1               
        
####################################################################################################
# def: _extract_tags()
####################################################################################################

def _extract_tags(item, publication):
    if item['data'].has_key('tags') and len(item['data']['tags']) > 0:
        for tag_item in item['data']['tags']:
            tag_name = tag_item['tag'].encode('utf-8')

            if _determine_if_tag_is_special(tag_name, publication):
                pass

            else:
                try:
                    tag = Tag.objects.get(slug=slugify(tag_name))

                except:
                    tag = Tag(
                        name=tag_name,
                    )

                    tag.save()

                publication_tag = PublicationTag(
                    tag=tag,
                    publication=publication,
                )

                publication_tag.save()        
        
####################################################################################################
# def: _save_zotero_extractor_log()
####################################################################################################

def _save_zotero_extractor_log(item, publication):
    zotero_extractor_log = ZoteroExtractorLog(
        item_key=item['key'],
        version=item['version'],
        publication=publication,
    )

    zotero_extractor_log.save()
        
        
####################################################################################################
# def: _save_attachement()
####################################################################################################

def _save_attachement(attachment_id, publication_slug, filename):
    zot = get_zotero_connection()
    item = zot.file(attachment_id)

    publication = Publication.objects.get(slug=publication_slug)
    path = publication_path(publication, filename)

    # If the directory doesn't exist, create it
    pdf_dir = getattr(settings, 'MEDIA_ROOT', None) + '/' + os.path.dirname(path)

    if not os.path.exists(pdf_dir):
        os.makedirs(pdf_dir)

    with open(getattr(settings, 'MEDIA_ROOT', None) + '/' + path, 'wb') as pdffile:
        pdffile.write(item)

    publication.pdf = path
    publication.save() 
    
####################################################################################################
# def: _extract_editors()
####################################################################################################

def _extract_editors(item):
    editors = []

    if item['data'].has_key('creators') and len(item['data']['creators']) > 0:
        for creator_item in item['data']['creators']:
            creator_type = creator_item['creatorType']

            if creator_type == 'editor':
                if 'name' in creator_item and creator_item['name'] != '':
                    editor_name = str(creator_item['name'].encode('utf-8'))
                    editor_first_surname = editor_name.split(' ')[-1]
                    editor_first_name = editor_name.replace(' ' + editor_first_surname, '')

                else:
                    editor_first_name = creator_item['firstName'].encode('utf-8')
                    editor_first_surname = creator_item['lastName'].encode('utf-8')

                editor_slug = slugify('%s %s' % (editor_first_name, editor_first_surname))

                try:
                    # Check if editor is in DB (comparing by slug)
                    editor = Person.objects.get(slug=editor_slug)

                except:
                    # If it isn't
                    try:
                        # Check if editor name correspond with any of the posible nicknames of the authors in DB
                        nick = Nickname.objects.get(slug=editor_slug)
                        editor = nick.person
                    except:
                        # If there is no reference to that person in the DB, create a new one
                        editor = Person(
                            first_name=editor_first_name,
                            first_surname=editor_first_surname
                        )

                        editor.save()

                editors.append(editor)

    return editors
    
####################################################################################################
# def: _save_publication_editors()
####################################################################################################

def _save_publication_editors(editors, publication):
    for editor in editors:
        publication_editor = PublicationEditor(
            editor=editor,
            publication=publication,
        )

        publication_editor.save()
        
####################################################################################################
# def: _determine_if_tag_is_special()
####################################################################################################

def _determine_if_tag_is_special(tag, publication):
    tag_slug = slugify(tag)
    jcr_match = re.match(JCR_PATTERN, tag.lower())

    project_slugs = Project.objects.all().values_list('slug', flat=True)

    special = True

    if (tag_slug == 'isi') and (publication.child_type in ['ConferencePaper', 'BookSection', 'JournalArticle']):
        publication.isi = True
        publication.save()

    elif (tag_slug == 'dblp') and (publication.child_type in ['ConferencePaper', 'BookSection', 'JournalArticle']):
        publication.dblp = True
        publication.save()

    elif (tag_slug in ['corea', 'core-a']) and (publication.child_type in ['ConferencePaper', 'BookSection']):
        publication.core = CORE_CHOICES[0][0]
        publication.save()

    elif (tag_slug in ['coreb', 'core-b']) and (publication.child_type in ['ConferencePaper', 'BookSection']):
        publication.core = CORE_CHOICES[1][0]
        publication.save()

    elif (tag_slug in ['corec', 'core-c']) and (publication.child_type in ['ConferencePaper', 'BookSection']):
        publication.core = CORE_CHOICES[2][0]
        publication.save()

    elif (tag_slug in ['q1', 'q-1']) and (publication.child_type == 'JournalArticle'):
        publication.parent_journal.quartile = QUARTILE_CHOICES[0][0]
        publication.parent_journal.save()

    elif (tag_slug in ['q2', 'q-2']) and (publication.child_type == 'JournalArticle'):
        publication.parent_journal.quartile = QUARTILE_CHOICES[1][0]
        publication.parent_journal.save()

    elif (tag_slug in ['q3', 'q-3']) and (publication.child_type == 'JournalArticle'):
        publication.parent_journal.quartile = QUARTILE_CHOICES[3][0]
        publication.parent_journal.save()

    elif (tag_slug in ['q4', 'q-4']) and (publication.child_type == 'JournalArticle'):
        publication.parent_journal.quartile = QUARTILE_CHOICES[3][0]
        publication.parent_journal.save()

    elif (jcr_match) and (publication.child_type == 'JournalArticle'):
        tag_lower = tag.lower().replace(',', '.')
        non_decimal = re.compile(r'[^\d.]+')

        impact_factor = non_decimal.sub('', tag_lower)

        publication.parent_journal.impact_factor = float(impact_factor)
        publication.parent_journal.save()

    elif tag_slug in project_slugs:
        project = Project.objects.get(slug=tag_slug)

        related_publication = RelatedPublication(
            project=project,
            publication=publication,
        )

        related_publication.save()

    else:
        special = False

    return special

        