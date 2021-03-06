# -*- encoding: utf-8 -*-

from django.shortcuts import render, get_object_or_404
from django.template.defaultfilters import slugify

from django.db.models import Sum, Min, Max

from .models import *
from .forms import *

from entities.projects.models import *


###     funding_program_index()
####################################################################################################

def funding_program_index(request):
    funding_programs = FundingProgram.objects.all().order_by('short_name')

    if request.method == 'POST':
        form = FundingProgramSearchForm(request.POST)
        if form.is_valid():
            query = form.cleaned_data['text']
            query = slugify(query)

            fps = []

            for funding_program in funding_programs:
                if (query in slugify(funding_program.full_name)) or (query in slugify(funding_program.short_name)):
                    fps.append(funding_program)

            funding_programs = fps

    else:
        form = FundingProgramSearchForm()

    return_dict = {
        'form': form,
        'funding_programs': funding_programs,
        'funding_programs_length': len(funding_programs),
    }

    return render(request, "funding_programs/index.html", return_dict)


###     funding_program_info(funding_program_slug)
####################################################################################################

def funding_program_info(request, funding_program_slug):
    funding_program = get_object_or_404(FundingProgram, slug=funding_program_slug)

    fundings = Funding.objects.filter(funding_program_id=funding_program.id)

    projects = Project.objects.filter(id__in=fundings.values('project_id'))

    dates = Project.objects.filter(id__in=fundings.values('project_id')).aggregate(min_year=Min('start_year'), max_year=Max('end_year'))

    min_year = dates['min_year']
    max_year = dates['max_year']

    number_of_projects = {}
    incomes = {}

    datum = []
    years = []

    for year in range(min_year, max_year + 1):
        years.append(year)
        number_of_projects[year] = 0
        for project in projects:
            if (project.start_year <= year) and (project.end_year >= year):
                number_of_projects[year] = number_of_projects[year] + 1

        income = FundingAmount.objects.filter(year=year, funding_id__in=fundings.values('id')).aggregate(value=Sum('own_amount'))
        if income['value'] is None:
            income['value'] = 0
        incomes[year] = float(income['value'])

        datum.append([year, number_of_projects[year], incomes[year]])

    projects = Project.objects.filter(id__in=fundings.values('project_id'))
    projects = projects.order_by('-start_year', '-end_year', 'full_name')

    funding_program_logos = FundingProgramLogo.objects.filter(funding_program=funding_program)

    return_dict = {
        'datum': datum,
        'funding_program': funding_program,
        'funding_program_logos': funding_program_logos,
        'max_year': max_year,
        'min_year': min_year,
        'projects': projects,
    }

    return render(request, "funding_programs/info.html", return_dict)
