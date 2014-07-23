from datetime import datetime
import json
import os
import re
import sys

from django.conf import settings
from django.db.models import Min, Max
from django.template import Context, loader
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

import config
from models import *
from signed_request import check_signature, BadSignature

_EPOCH = datetime(1970, 1, 1)

# timedelta.total_seconds added in 2.7
if hasattr(timedelta, 'total_seconds'):
    def unix_time(dt):
        total_seconds(dt - _EPOCH)
else:
    def unix_time(dt):
        td = dt - _EPOCH
        return float(td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6

def home(request):
    t = loader.get_template('metrics/home.html')

    time_range = Report.objects.aggregate(min=Min('pull_time'), max=Max('pull_time'));

    c = Context({
        'page_name': 'home',
        'metrics': config.Metric.all(),
        'min_time': unix_time(time_range['min']),
        'max_time': unix_time(time_range['max']),
        'targets': config.Target.all()
    })
    return HttpResponse(t.render(c))

def machines(request):
    return HttpResponse("MACHINES")

def metric(request, metric_name):
    try:
        metric = config.Metric.get(metric_name)
    except KeyError:
        return HttpResponseNotFound("No such metric")

    t = loader.get_template('metrics/metric.html')
    time_range = Report.objects \
                   .aggregate(min=Min('pull_time'), max=Max('pull_time'));

    c = Context({
        'page_name': 'metric',
        'metric': metric,
        'min_time': unix_time(time_range['min']),
        'max_time': unix_time(time_range['max']),
        'targets': config.Target.all()
    })
    return HttpResponse(t.render(c))

def target(request, machine_name, partition_name, tree_name, testset_name):
    target_name = machine_name + '/' + partition_name + '/' + tree_name + '/' + testset_name
    try:
        target = config.Target.get(target_name)
    except KeyError:
        return HttpResponseNotFound("No such target")

    t = loader.get_template('metrics/target.html')
    time_range = Report.objects \
                   .filter(target__name=target.name) \
                   .aggregate(min=Min('pull_time'), max=Max('pull_time'));

    c = Context({
        'page_name': 'target',
        'target': target,
        'machine': target.partition.machine,
        'partition': target.partition,
        'tree': target.tree,
        'testset': target.testset,
        'metrics': config.Metric.all(),
        'min_time': unix_time(time_range['min']),
        'max_time': unix_time(time_range['max']),
        'targets': config.Target.all()
    })
    return HttpResponse(t.render(c))

_SUMMARY_CLASSES = {
    'none': None,
    'hour6': SummaryHour6,
    'day': SummaryDay,
    'week': SummaryWeek,
    'month': SummaryMonth
}

def values(request):
    target = None
    target_name = request.GET.get('target', None)
    if target_name is not None:
        try:
            target = config.Target.get(target_name)
        except KeyError:
            return HttpResponseNotFound("No such target")

    metric = None
    metric_name = request.GET.get('metric', None)
    if metric_name is not None:
        try:
            metric = config.Metric.get(metric_name)
        except KeyError:
            return HttpResponseNotFound("No such metric")

    start = None
    start_str = request.GET.get('start', None)
    if start_str:
        m = re.match(r'(\d\d\d\d)-(\d\d)-(\d\d)$', start_str)
        if m is not None:
            try:
                start = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
        if start is None:
            return HttpResponseBadRequest("Invalid start date")

    end = None
    end_str = request.GET.get('end', None)
    if end_str:
        m = re.match(r'(\d\d\d\d)-(\d\d)-(\d\d)$', end_str)
        if m is not None:
            try:
                end = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))) + timedelta(hours=24)
            except ValueError:
                pass
        if end is None:
            return HttpResponseBadRequest("Invalid end date")

    group = request.GET.get('group', 'none')
    if not group in _SUMMARY_CLASSES:
        return HttpResponseBadRequest("Invalid group type")

    result = []

    summaryCls = _SUMMARY_CLASSES[group]
    if summaryCls is None:
        qs = Value.objects.all()
        if start:
            qs = qs.filter(report__pull_time__gte=start)
        if end:
            qs = qs.filter(report__pull_time__lt=end)
        if target:
            qs = qs.filter(report__target__name=target.name)
        if metric:
            qs = qs.filter(metric__name=metric.name)

        qs = qs.order_by('metric', 'report__target', 'report__pull_time')

        last_metric = None
        last_target = None

        a = dict()
        for value in qs:
            metric_name = value.metric.name
            if metric_name != last_metric:
                metric_data = {
                    'name': metric_name,
                    'targets': []
                }
                result.append(metric_data)
                last_metric = metric_name
                last_target = None

            target_name = value.report.target.name
            if target_name != last_target:
                target_data = {
                    'name': target_name,
                    'values': []
                }
                metric_data['targets'].append(target_data)
                last_target = target_name

            target_data['values'].append({
                'time': unix_time(value.report.pull_time),
                'value': value.value
            })
    else:
        summaries = summaryCls.get_summaries(start, end, target, metric)

        last_metric = None
        last_target = None

        a = dict()
        for summary in summaries:
            metric_name = summary.metric.name
            if metric_name != last_metric:
                metric_data = {
                    'name': metric_name,
                    'targets': []
                }
                result.append(metric_data)
                last_metric = metric_name
                last_target = None

            target_name = summary.target.name
            if target_name != last_target:
                target_data = {
                    'name': target_name,
                    'values': []
                }
                metric_data['targets'].append(target_data)
                last_target = target_name

            target_data['values'].append({
                'time': unix-time(summary.time),
                'avg': summary.avg_value,
                'min': summary.min_value,
                'max': summary.max_value,
            })

    return HttpResponse(json.dumps(result), "application/json")

# Encoding detection for JSON rfc4627, section 3. The RFC doesn't mention
# the possibility of starting with a BOM, but in pratice that's likely
# if the input data is UTF-16.
def application_json_to_unicode(raw):
    bom = True
    if raw[0:2] == '\xfe\xff':
        encoding = 'UTF-16BE'
    elif raw[0:2] == '\xff\xfe':
        encoding = 'UTF-16LE'
    elif raw[0:3] == '\xef\xbb\xbf':
        encoding = 'UTF-8'
    elif raw[0:4] == '\x00\x00\xfe\xff':
        encoding = 'UTF-32BE'
    elif raw[0:4] == '\xff\xfe\x00\x00':
        encoding = 'UTF-32LE'
    else:
        bom = False
        null_patterns = {
            'NNNX': 'UTF-32BE',
            'NXNX': 'UTF-16BE',
            'XNNN': 'UTF-32LE',
            'XNXN': 'UTF-16LE'
        };

        nullPattern = re.sub(r'[^\x00]', 'X', raw[0:4])
        nullPattern = re.sub(r'\x00', 'N', nullPattern)

        if nullPattern in null_patterns:
            encoding = encodings[nullPattern]
        else:
            encoding = 'UTF-8'

    # json module can't handle initial bom, so strip if we found it
    decoded = raw.decode(encoding)
    if bom:
        return decoded[1:]
    else:
        return decoded

class ValidationError(Exception):
    pass

def child(parent, key):
    val = parent.get(key, None)
    if val is None:
        raise ValidationError("'%s' is missing")
    return val

def child_string(parent, key):
    val = child(parent, key)
    if not isinstance(val, basestring):
        raise ValidationError("'%s' is not a string" % key)
    else:
        return val

def child_number(parent, key):
    val = child(parent, key)
    if not (isinstance(val, int) or isinstance(val, float)):
        raise ValidationError("'%s' is not a number" % key)
    else:
        return val

def child_array(parent, key):
    val = child(parent, key)
    if not isinstance(val, list):
        raise ValidationError("'%s' is not a array" % key)
    else:
        return val

def process_report(data, machine_name):
    # We validate everything before we start updating the database

    if not isinstance(data, dict):
        raise ValidationError("Report toplevel should be an object")

    machine_in_json = data.get('machine', None)
    if machine_in_json != machine_name:
        raise ValidationError("Report isn't for expected machine")

    partition_name = child_string(data, 'partition')
    tree_path = child_string(data, 'tree')
    testset_name = child_string(data, 'testset')

    tree = None
    for t in config.Tree.all():
        if t.path == tree_path:
            tree = t
    if tree is None:
        raise ValidationError("Can't find tree '%s'" % tree_path)

    target_name = '/'.join((machine_name, partition_name, tree.name, testset_name))
    try:
        target = config.Target.get(target_name)
    except KeyError:
        raise ValidationError("Can't find target '%s'" % target_name)

    revision = child_string(data, 'revision')
    if not re.match('^[a-f0-9]{64}$', revision):
        raise ValidationError("Property 'revision' doesn't have the expected format")

    pull_time_str = child_string(data, 'pullTime')
    try:
        pull_time = datetime.strptime(pull_time_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        raise ValidationError("Can't parse property 'pullTime'")

    metrics_data = child_array(data, 'metrics')
    for metric_data in metrics_data:
        if not isinstance(metric_data, dict):
            raise ValidationError("metric is not an object")

        metric_name = child_string(metric_data, 'name')
        try:
            metric = config.Metric.get(metric_name)
        except KeyError:
            raise ValidationError("unknown metric '%s'" % metric_name)

        metric_value = child_number(metric_data, 'value')

    # Now actually store into the database

    (target_dbobj, _) = Target.objects.get_or_create(name=target_name,
                                                     defaults= {
                                                         'machine': machine_name,
                                                         'partition': partition_name,
                                                         'tree': tree.name,
                                                         'testset': testset_name
                                                     })
    report = Report(target=target_dbobj,
                    revision=revision,
                    pull_time=pull_time)
    report.save()

    for metric_data in metrics_data:
        metric_name = child_string(metric_data, 'name')
        metric = config.Metric.get(metric_name)
        metric_value = child_number(metric_data, 'value')

        (metric_dbobj, _) = Metric.objects.get_or_create(name=metric_name)

        value = Value(report=report,
                      metric=metric_dbobj,
                      value=metric_value)
        value.save()

@require_POST
@csrf_exempt
def upload(request):
    machine_name = request.GET.get('machine', None)
    if machine_name is None:
        return HttpResponseBadRequest("No machine= parameter in URL")

    try:
        machine = config.Machine.get(machine_name)
    except KeyError:
        return HttpResponseNotFound("No such machine")

    pubkey_path = os.path.join(settings.CONFIG_ROOT, 'machines', machine.name + '.pubkey')

    try:
        check_signature(request, pubkey_path)
    except BadSignature, e:
        return HttpResponseBadRequest("Signature check failed: " + e.message)

    toload = application_json_to_unicode(request.raw_post_data)
    try:
        data = json.loads(toload)
    except ValueError, e:
        return HttpResponseBadRequest("Can't parse data")

    try:
        process_report(data, machine_name)
    except ValidationError, e:
        return HttpResponseBadRequest(e.message)

    return HttpResponse("OK\n")
