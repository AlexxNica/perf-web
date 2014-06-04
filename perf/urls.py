from django.conf.urls import patterns, include, url

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', 'metrics.views.home', name='home'),
    url(r'^machines$', 'metrics.views.machines'),
    url(r'^metric/(?P<metric_name>[^/]+)$', 'metrics.views.metric'),
    url(r'^target/(?P<machine_name>[^/]+)/(?P<partition_name>[^/]+)/(?P<tree_name>[^/]+)/(?P<testset_name>[^/]+)$', 'metrics.views.target'),
    # target=MACHINE/PARTITION/TREE/TESTSET, metric=METRIC, start=YYYY-MM-YY, end=YYYY-MM-YY, group=none|hour6|day|week|month
    url(r'^api/values$', 'metrics.views.values'),
    url(r'^api/upload$', 'metrics.views.upload')
)
