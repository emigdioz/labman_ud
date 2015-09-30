# -*- encoding: utf-8 -*-

from django.conf import settings
from django.contrib import admin

from .linked_data import *
from .models import *


###		PersonSeeAlsoInline
####################################################################################################

class PersonSeeAlsoInline(admin.TabularInline):
    model = PersonSeeAlso
    extra = 0


###		AccountProfileInline
####################################################################################################

class AccountProfileInline(admin.TabularInline):
    model = AccountProfile
    extra = 1


###		NicknameInline
####################################################################################################

class NicknameInline(admin.TabularInline):
    model = Nickname
    extra = 0

    exclude = ['slug']


###		JobInline
####################################################################################################

class JobInline(admin.StackedInline):
    model = Job
    extra = 1


###		PersonAdmin
####################################################################################################

class PersonAdmin(admin.ModelAdmin):
    model = Person

    def delete_model(modeladmin, request, queryset):
        for obj in queryset:
            if getattr(settings, 'ENABLE_RDF_PUBLISHING', False):
                delete_person_rdf(obj)
            obj.delete()

    search_fields = ['full_name', 'slug']
    list_display = ['full_name', 'email', 'is_active']
    list_filter = ['is_active']
    inlines = [
        PersonSeeAlsoInline,
        AccountProfileInline,
        NicknameInline,
        JobInline,
    ]
    exclude = [
        'full_name',
        'slug',
        'safe_biography',
    ]
    actions = [
        delete_model,
    ]


###		AccountProfileAdmin
####################################################################################################

class AccountProfileAdmin(admin.ModelAdmin):
    model = AccountProfile

    def delete_model(modeladmin, request, queryset):
        for obj in queryset:
            if getattr(settings, 'ENABLE_RDF_PUBLISHING', False):
                delete_account_profile_rdf(obj)
            obj.delete()

    actions = [
        delete_model,
    ]


###		NicknameAdmin
####################################################################################################

class NicknameAdmin(admin.ModelAdmin):
    model = Nickname

    def delete_model(modeladmin, request, queryset):
        for obj in queryset:
            if getattr(settings, 'ENABLE_RDF_PUBLISHING', False):
                delete_nickname_rdf(obj)
            obj.delete()

    search_fields = ['nickname', 'slug']
    list_display = ['nickname', 'slug']
    exclude = ['slug']
    actions = [
        delete_model,
    ]


####################################################################################################
####################################################################################################
###   Register classes
####################################################################################################
####################################################################################################

admin.site.register(Person, PersonAdmin)
admin.site.register(AccountProfile, AccountProfileAdmin)
admin.site.register(Nickname, NicknameAdmin)

admin.site.disable_action('delete_selected')
