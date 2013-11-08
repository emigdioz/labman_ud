# coding: utf-8

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.template.defaultfilters import slugify

from django.conf import settings

from .models import Publication, PublicationAuthor, PublicationTag, PublicationType
from .forms import PublicationSearchForm

from entities.projects.models import Project, RelatedPublication

from entities.persons.models import Person

from entities.utils.models import Tag


# Create your views here.

PAGINATION_NUMBER = settings.PUBLICATIONS_PAGINATION


###########################################################################
# View: publication_index
###########################################################################

def publication_index(request, tag_slug=None, publication_type_slug=None):
    tag = None
    publication_type = None

    query_string = None

    clean_index = False

    if tag_slug:
        tag = Tag.objects.get(slug=tag_slug)
        publication_ids = PublicationTag.objects.filter(tag=tag).values('publication_id')
        publications = Publication.objects.filter(id__in=publication_ids)

    if publication_type_slug:
        publication_type = PublicationType.objects.get(slug=publication_type_slug)
        publications = Publication.objects.filter(publication_type=publication_type.id)

    if not tag_slug and not publication_type_slug:
        clean_index = True
        publications = Publication.objects.all()

    publications = publications.order_by('-year', '-title').exclude(authors=None)

    if request.method == 'POST':
        form = PublicationSearchForm(request.POST)
        if form.is_valid():
            query_string = form.cleaned_data['text']
            query = slugify(query_string)

            pubs = []

            person_ids = Person.objects.filter(slug__contains=query).values('id')
            publication_ids = PublicationAuthor.objects.filter(author_id__in=person_ids).values('publication_id')
            publication_ids = set([x['publication_id'] for x in publication_ids])

            for publication in publications:
                if (query in slugify(publication.title)) or (publication.id in publication_ids):
                    pubs.append(publication)

            publications = pubs
            clean_index = False

    else:
        form = PublicationSearchForm()

    publications_length = len(publications)

    paginator = Paginator(publications, PAGINATION_NUMBER)

    page = request.GET.get('page')

    try:
        publications = paginator.page(page)

    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        publications = paginator.page(1)

    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        publications = paginator.page(paginator.num_pages)

    return render_to_response('publications/index.html', {
            'publications': publications,
            'form': form,
            'publications_length': publications_length,
            'tag': tag,
            'publication_type': publication_type,
            'query_string': query_string,
            'clean_index': clean_index,
        },
        context_instance=RequestContext(request))


#########################
# View: publication_info
#########################

def publication_info(request, slug):

    publication = get_object_or_404(Publication, slug=slug)

    author_ids = PublicationAuthor.objects.filter(publication=publication.id).values('author_id').order_by('position')
    authors = []

    for _id in author_ids:
        author = Person.objects.get(id=_id['author_id'])
        authors.append(author)

    related_projects_ids = RelatedPublication.objects.filter(publication=publication.id).values('project_id')
    related_projects = Project.objects.filter(id__in=related_projects_ids)

    related_publications_ids = RelatedPublication.objects.filter(project_id__in=related_projects_ids).values('publication_id')
    related_publications = Publication.objects.filter(id__in=related_publications_ids).exclude(id=publication.id)

    tag_ids = PublicationTag.objects.filter(publication=publication.id).values('tag_id')
    tags = Tag.objects.filter(id__in=tag_ids).order_by('name')
    # tags = tags.extra(select={'length': 'Length(name)'}).order_by('length')

    try:
        pdf = publication.pdf
    except:
        pdf = None

    try:
        parent_publication = Publication.objects.get(id=publication.part_of.id)
    except:
        parent_publication = None

    bibtex = publication.bibtex.replace(",", ",\n")

    return render_to_response('publications/info.html', {
            'publication': publication,
            'authors': authors,
            'related_projects': related_projects,
            'related_publications': related_publications,
            'tags': tags,
            'pdf': pdf,
            'parent_publication': parent_publication,
            'bibtex': bibtex,
        },
        context_instance=RequestContext(request))


#########################
# View: publication_tag_cloud
#########################

def publication_tag_cloud(request):

    tag_dict = {}

    tags = PublicationTag.objects.all()

    for tag in tags:
        t = tag.tag.name
        if t in tag_dict.keys():
            tag_dict[t] = tag_dict[t] + 1
        else:
            tag_dict[t] = 1

    return render_to_response('publications/tag_cloud.html', {
            'tag_dict': tag_dict,
        },
        context_instance=RequestContext(request))
