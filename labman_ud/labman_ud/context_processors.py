
from django.conf import settings

from labman_setup.models import *


def global_vars(request):

    try:
        _settings = LabmanDeployGeneralSettings.objects.get()

    except:
        return {
            'INITIAL_SETUP': True,
        }

    social_profiles = OfficialSocialProfile.objects.all().order_by('name')
    seo_and_analytics = SEOAndAnalytics.objects.first()

    footer_sections = 0
    address_details = False
    contact_details = False
    social_details = False

    if (_settings.address):
        footer_sections += 1
        address_details = True

    if (_settings.email_address or _settings.contact_person or _settings.phone_number):
        footer_sections += 1
        contact_details = True

    if (len(social_profiles) > 0):
        footer_sections += 1
        social_details = True

    if footer_sections in (0, 1):
        footer_divisions_width = 12

    elif footer_sections == 2:
        footer_divisions_width = 6

    else:
        footer_divisions_width = 4

    if (len(social_profiles) <= 3):
        social_profile_width = 3

    elif (len(social_profiles) <= 5):
        social_profile_width = 2

    else:
        social_profile_width = 1

    return_dict = {
        'RESEARCH_GROUP_SETTINGS': _settings,
        'RDF_URI': getattr(settings, 'GRAPH_BASE_URL', None) + '/',
        'TEAM_IMAGE_PATH': getattr(settings, 'TEAM_IMAGE_PATH', None) + '',
        'FOOTER_DIVISIONS_WIDTH': footer_divisions_width,
        'ADDRESS_DETAILS': address_details,
        'CONTACT_DETAILS': contact_details,
        'SOCIAL_DETAILS': social_details,
        'SOCIAL_PROFILES': social_profiles,
        'SOCIAL_PROFILE_WIDTH': social_profile_width,
        'SEO_AND_ANALYTICS': seo_and_analytics,
    }

    return return_dict
