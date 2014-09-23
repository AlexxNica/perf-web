from datetime import datetime
import json
import os
import re
import sys

from django.conf import settings
from django.db.models import Min, Max
from django.core.exceptions import ObjectDoesNotExist
from django.template import Context, loader
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseBadRequest
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

import config
from models import *
from signed_request import check_signature, BadSignature

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

# timedelta.total_seconds added in 2.7
if hasattr(timedelta, 'total_seconds'):
    def unix_time(dt):
        return int(round((dt - _EPOCH).total_seconds()))
else:
    def unix_time(dt):
        td = dt - _EPOCH
        return int(round(float(td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6))

def home(request):
    t = loader.get_template('metrics/home.html')

    time_range = Report.objects \
         .filter(error='') \
         .aggregate(min=Min('pull_time'), max=Max('pull_time'));
    if time_range['min'] is None:
        time_range['min'] = time_range['max'] = timezone.now()

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
                       .filter(error='') \
                       .aggregate(min=Min('pull_time'), max=Max('pull_time'));
    if time_range['min'] is None:
        time_range['min'] = time_range['max'] = timezone.now()

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
                   .filter(target__name=target.name, error='') \
                   .aggregate(min=Min('pull_time'), max=Max('pull_time'));
    if time_range['min'] is None:
        time_range['min'] = time_range['max'] = timezone.now()

    error_report = None
    error_time = None
    try:
        error_report = Report.objects.filter(target__name=target_name).exclude(error='').latest('pull_time')
        error_time = unix_time(error_report.pull_time)
    except ObjectDoesNotExist:
        pass

    c = Context({
        'page_name': 'target',
        'target': target,
        'machine': target.partition.machine,
        'partition': target.partition,
        'tree': target.tree,
        'testset': target.testset,
        'error_report': error_report,
        'error_time': error_time,
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
                start = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
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
                end = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc) + timedelta(hours=24)
            except ValueError:
                pass
        if end is None:
            return HttpResponseBadRequest("Invalid end date")

    group = request.GET.get('group', 'none')
    if not group in _SUMMARY_CLASSES:
        return HttpResponseBadRequest("Invalid group type")

    result = {}
    result['metrics'] = metrics = []

    summaryCls = _SUMMARY_CLASSES[group]
    if summaryCls is None:
        target_map = {}

        qs = Value.objects.all()
        qs = Value.filter_and_order(qs, start, end, metric, target)

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
                metrics.append(metric_data)
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

                if target_name in target_map:
                    revisions = target_map[target_name]
                else:
                    revisions = target_map[target_name] = {}

            pull_time_str = str(unix_time(value.report.pull_time))
            if not pull_time_str in revisions:
                revisions[pull_time_str] = value.report.revision

            target_data['values'].append({
                'time': unix_time(value.report.pull_time),
                'value': value.value
            })

        result['targets'] = targets = []
        for name, revisions in target_map.iteritems():
            targets.append({'name': name,
                            'revisions': revisions});
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
                metrics.append(metric_data)
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
                'time': unix_time(summary.time),
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
        raise ValidationError("'%s' is missing" % key)
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
        pull_time = datetime.strptime(pull_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        pull_time = pull_time + timedelta(seconds=target.partition.machine.time_adjust_sec)
    except ValueError:
        raise ValidationError("Can't parse property 'pullTime'")

    error = None
    log = None
    metrics_data = None
    if 'error' in data:
        error = child_string(data, 'error')
        log = child_array(data, 'log')
    else:
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
                    pull_time=pull_time,
                    error=error if error is not None else '')
    report.save()
    if log is not None:
        log_dir = os.path.join(settings.LOG_ROOT, target_name.replace('/', '-'))
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_path = os.path.join(log_dir,
                                pull_time.strftime('%Y-%m-%d-%H:%M:%S') + '-' + revision + '.json')
        with open(log_path, 'w') as fp:
            json.dump(log, fp)

    if metrics_data is not None:
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

    toload = application_json_to_unicode(request.body)
    try:
        data = json.loads(toload)
    except ValueError, e:
        return HttpResponseBadRequest("Can't parse data")

    try:
        process_report(data, machine_name)
    except ValidationError, e:
        return HttpResponseBadRequest(e.message)

    return HttpResponse("OK\n")

_PRIORITY_RE = re.compile('^[0-7]$')
_LINE_RE = re.compile('^([^\n]*(?:\n[^\n]*){2})\n')
_ESCAPE_RE = re.compile(r'\0x1b[0-9;]+m')
# C0 and C1 control characters, DEL, except for \t\n
_UNICODE_CONTROL_RE = re.compile(r'[\x00-\x08\x0A-\x1F\x7F-\x9F]')

def escape_character(m):
    c = m.group(0)
    if c == '\n':
        return '\\n'
    elif c == '\r':
        return '\\r'
    else:
        return '\\x%02x' % ord(c)

def log(request, machine_name, partition_name, tree_name, testset_name, report_id, format):
    target_name = machine_name + '/' + partition_name + '/' + tree_name + '/' + testset_name
    try:
        target = config.Target.get(target_name)
    except KeyError:
        return HttpResponseNotFound("No such target")

    try:
        report = Report.objects.get(id=report_id,
                                    target__name=target.name)
    except ObjectDoesNotExist:
        return HttpResponseNotFound("No such log")

    log_path = os.path.join(settings.LOG_ROOT,
                            target.name.replace('/', '-'),
                            report.pull_time.strftime('%Y-%m-%d-%H:%M:%S') + '-' + report.revision + '.json')
    try:
        fp = open(log_path, 'r')
    except IOError, e:
        return HttpResponseNotFound("Log has been purged")

    if format == 'json':
        # Could using StreamingHttpResponse; as below Django will just
        # pile the chunks up in an array
        response = HttpResponse(content_type="application/json")
        while True:
            buf = fp.read(32*1024)
            if buf == '':
                break
            response.write(buf)
    else:
        if format == 'html':
            response = HttpResponse(content_type="text/html; charset=utf-8")
            response.write('''<!DOCTYPE html><html>
<head>
  <title>%s - %s</title>
  <style type="text/css">
     .error { color: red; }
     .notice { font-weight: bold; }
  </style>
</head>
<body><pre>''' % (report.pull_time.strftime('%Y-%m-%d %H:%M:%S'), target_name))
        else:
            response = HttpResponse(content_type="text/plain; charset=utf-8")
        log = json.load(fp)
        for record in log:
            # We write out log records in roughly the same format as
            # the journalctl -o iso-short format
            try:
                time = long(record['_SOURCE_REALTIME_TIMESTAMP'])
            except KeyError:
                time = 0
            if time == 0:
                for f in record['__CURSOR'].split(';'):
                    if f.startswith('t='):
                        time = long(f[2:], 16)
            dt = datetime.utcfromtimestamp(time/1000000)
            # This is like journalctl -o short-iso; default is '%b %d %H:%M:%S'
            response.write(dt.strftime('%Y-%m-%dT%H:%M:%S%z '))

            # journalctl shows the hostname here - that isn't interesting for us
            #
            # try:
            #    response.write(record['_HOSTNAME'])
            # except KeyError:
            #    pass
            #
            # response.write(' ')

            try:
                response.write(record['SYSLOG_IDENTIFIER'])
            except KeyError:
                response.write(record['_COMM'])

            pid = None
            try:
                pid = record['_PID']
            except KeyError:
                try:
                    pid = record['_SYSLOG_PID']
                except KeyError:
                    pass
            if pid != None:
                response.write('[')
                response.write(pid)
                response.write(']')

            response.write(': ')

            message = record['MESSAGE']

            # If the message was an escaped blob, try to convert it to text
            if type(message) == list:
                message = ''.join((chr(x) for x in message))
                try:
                    message = unicode(message, 'UTF-8')
                except UnicodeDecodeError:
                    # journalctl falls back to printing the bytes, this seems more useful
                    message = repr(message)[1:-1]

            # 300 characters or 3 lines, whichever is less; journalctl does
            # a more sophisticated approach to ellipsization where it ellipsizes
            # middle lines
            if len(message) > 300:
                message = message[0:300] + "..."
            m = _LINE_RE.match(message)
            if m:
                message = m.group(1) + "..."

            # For multi-line log messages, journalctl indents subsequent lines
            # with spaces to have the same indent as the first line has
            # pre-message text, but multi-line log messages are quite rare
            # so we skip that

            # Remove ANSI color escapes and replace tabs with 8 spaces
            message = _ESCAPE_RE.sub('', message)
            message = message.replace("\t", "        ")

            # Escape control characters; again journalctl would just print
            # the message as bytes
            message = _UNICODE_CONTROL_RE.sub(escape_character, message)

            # For HTML mode, use bold/red to mark different priorities
            if format == 'html':
                priority = 6 # Info
                try:
                    priority_str = record['PRIORITY']
                    if _PRIORITY_RE.match(priority_str):
                        priority = int(priority_str)
                except KeyError:
                    pass

                if priority <= 3: # error
                    response.write('<span class="error">');
                    response.write(message)
                    response.write('</span>')
                elif priority <= 5:  #notice
                    response.write('<span class="notice">');
                    response.write(message)
                    response.write('</span>')
                else:
                    response.write(message)
            else:
                response.write(message)

            response.write('\n')

        if format == 'html':
            response.write('</pre></body')

    fp.close()

    return response
