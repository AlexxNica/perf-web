from datetime import datetime, timedelta
from django.db import models
import sys

class Metric(models.Model):
    name = models.CharField(max_length=255)

class Target(models.Model):
    name = models.CharField(max_length=255)
    machine = models.CharField(max_length=32)
    partition = models.CharField(max_length=32)
    tree = models.CharField(max_length=255)
    testset = models.CharField(max_length=32)

class Report(models.Model):
    target = models.ForeignKey(Target)
    revision = models.CharField(max_length=64)
    pull_time = models.DateTimeField()

class Value(models.Model):
    report = models.ForeignKey(Report)
    metric = models.ForeignKey(Metric)
    value = models.FloatField()

    @staticmethod
    def filter_and_order(qs, start=None, end=None, metric=None, target=None):
        if start is not None:
            qs = qs.filter(report__pull_time__gte=start)
        if end is not None:
            qs = qs.filter(report__pull_time__lt=end)
        if metric is not None:
            qs = qs.filter(metric__name=metric.name)
        if target is not None:
            qs = qs.filter(report__target__name=target.name)

        return qs.order_by('metric', 'report__target', 'report__pull_time')

def resummarize():
    # We give machines a 6 hours grace period to update results
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=6)

    SummaryHour6.save_summaries(cutoff)
    SummaryDay.save_summaries(cutoff)
    SummaryWeek.save_summaries(cutoff)
    SummaryMonth.save_summaries(cutoff)

class Summary(models.Model):
    time = models.DateTimeField()
    target = models.ForeignKey(Target)
    metric = models.ForeignKey(Metric)
    min_value = models.FloatField()
    max_value = models.FloatField()
    avg_value = models.FloatField()
    count = models.IntegerField()

    class Meta:
        abstract = True

    @classmethod
    def last_summary_end(cls):
        last_summary_start = cls.objects.aggregate(models.Max('time'))['time__max']
        if last_summary_start is not None:
            return cls.time_next(last_summary_start)
        else:
            return None

    @classmethod
    def get_summaries(cls, start, end, target=None, metric=None):
        if start is not None:
            start_truncated = cls.time_truncate(start)
        else:
            start_truncated = None

        if end is not None:
            end_truncated = cls.time_truncate(end)
            if end_truncated != end:
                end_truncated = cls.time_next(end_truncated)
        else:
            end_truncated = None

        qs = cls.filter_and_order(cls.objects.all(),
                                  start=start_truncated, end=end_truncated,
                                  target=target, metric=metric)

        result = list(qs)

        if start_truncated is not None:
            last_summary_end = cls.last_summary_end()
            if last_summary_end is not None:
                start_truncated = max(start_truncated, last_summary_end)

        cls._do_summarize(start=start_truncated,
                          end=end_truncated,
                          target=target,
                          metric=metric,
                          append_unsaved=result)

        return result

    @classmethod
    def save_summaries(cls, cutoff):
        cls._do_summarize(start=cls.last_summary_end(),
                            end=cls.time_truncate(cutoff))

    @classmethod
    def _do_summarize(cls, start, end, target=None, metric=None, append_unsaved=None):
        if append_unsaved is not None and cls.finer != Value:
            qs = cls.finer.get_summaries(start, end, target=target, metric=metric)
        else:
            qs = cls.finer.filter_and_order(cls.finer.objects.all(),
                                            start=start, end=end, target=target, metric=metric)
        last_metric = None
        last_target  = None
        last_truncated  = None
        total_min_value = None
        total_max_value = None
        total_value = None
        total_count = 0

        for row in qs:
            if cls.finer == Value:
                target = row.report.target
                time = row.report.pull_time
                min_value = max_value = avg_value = row.value
                count = 1
            else:
                target = row.target
                time = row.time
                min_value = row.min_value
                max_value = row.max_value
                avg_value = row.avg_value
                count = row.count

            truncated = cls.time_truncate(time)
            if last_metric != row.metric or last_target != target or truncated != last_truncated:
                if total_count > 0:
                    summary = cls(time=last_truncated,
                                  target=last_target,
                                  metric=last_metric,
                                  min_value=total_min_value,
                                  max_value=total_max_value,
                                  avg_value=(total_value/total_count),
                                  count=total_count)
                    if append_unsaved is not None:
                        append_unsaved.append(summary)
                    else:
                        summary.save()

                total_min_value = min_value
                total_max_value = max_value
                total_value = avg_value * count
                total_count = count
                last_metric = row.metric
                last_target = target
                last_truncated = truncated
            else:
                total_min_value = min(total_min_value, min_value)
                total_max_value = max(total_max_value, max_value)
                total_value += avg_value * count
                total_count += count

        if total_count > 0:
            summary = cls(time=last_truncated,
                          target=last_target,
                          metric=last_metric,
                          min_value=total_min_value,
                          max_value=total_max_value,
                          avg_value=(total_value/total_count),
                          count=total_count)
            if append_unsaved is not None:
                append_unsaved.append(p)
            else:
                summary.save()

    @staticmethod
    def filter_and_order(qs, start=None, end=None, metric=None, target=None):
        if start is not None:
            qs = qs.filter(time__gte=start)
        if end is not None:
            qs = qs.filter(time__lt=end)
        if metric is not None:
            qs = qs.filter(metric__name=metric.name)
        if target is not None:
            qs = qs.filter(target__name=target.name)

        return qs.order_by('target', 'metric', 'time')

class SummaryHour6(Summary):
    @staticmethod
    def time_truncate(dt):
        return dt.replace(hour=dt.hour-dt.hour%6, minute=0, second=0, microsecond=0)

    @staticmethod
    def time_next(dt):
        return dt + timedelta(hours=6)

    finer = Value

class SummaryDay(Summary):
    @staticmethod
    def time_truncate(dt):
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def time_next(dt):
        return dt + timedelta(days=1)

    finer = SummaryHour6

class SummaryWeek(Summary):
    @staticmethod
    def time_truncate(dt):
        tmp =  dt.replace(hour=0, minute=0, second=0, microsecond=0)
        # Monday as week start
        return tmp - timedelta(dt.weekday())

    @staticmethod
    def time_next(dt):
        return dt + timedelta(weeks=1)

    finer = SummaryDay

class SummaryMonth(Summary):
    @staticmethod
    def time_truncate(dt):
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def time_next(dt):
        if dt.month == 12:
            return dt.replace(year=dt.year + 1, month=1)
        else:
            return dt.replace(month=dt.month + 1)

    # A month isn't exactly 4 weeks, so we have to summarize from days
    finer = SummaryDay
