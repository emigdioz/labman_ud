from django.conf.urls import patterns, url
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = patterns('',
    url(r'^$', 'charts.views.chart_index', name = 'chart_index'),
    url(r'^incomes_by_year/$', 'charts.views.incomes_by_year', name = 'incomes_by_year'),
)

urlpatterns += staticfiles_urlpatterns()