import ConfigParser
import os
import re

from django.conf import settings

class Configuration:
    def __init__(self):
        self.errors = []
        self.objects = {}

    def _add_error(self, f, section, error):
        self.errors.append('%s [%s]: %s' % (f, section, error))

    def _add_object(self, cls, f, parser, section):
        obj = cls()

        name = section[len(cls.__name__) + 1:]
        m = re.match(obj.name_pattern + '$', name)
        if m is None:
            self._add_error(f, section, "name not valid for " + cls.__name__)
            return

        obj.name = name
        for g in m.groupdict():
            setattr(obj, g, m.group(g))

        try:
            obj._load(parser, section)
        except ConfigParser.NoOptionError, e:
            self._add_error(f, section, 'missing key ' + e.option)

        obj.filename = f
        obj.section = section

        clsname = cls.__name__

        if not clsname in self.objects:
            self.objects[clsname] = {}

        if name in self.objects[clsname]:
            self._add_error(f, section, 'duplicate object')
        else:
            self.objects[clsname][name] = obj

    def _load_file(self, f):
        parser = ConfigParser.RawConfigParser()
        parser.read(os.path.join(settings.CONFIG_ROOT, f))

        for section in parser.sections():
            if section.startswith('machine '):
                self._add_object(Machine, f, parser, section)
            elif section.startswith('metric '):
                self._add_object(Metric, f, parser, section)
            elif section.startswith('partition '):
                self._add_object(Partition, f, parser, section)
            elif section.startswith('target '):
                self._add_object(Target, f, parser, section)
            elif section.startswith('testset '):
                self._add_object(TestSet, f, parser, section)
            elif section.startswith('tree '):
                self._add_object(Tree, f, parser, section)
            else:
                self._add_error(f, section, 'Unknown section')

    def load(self):
        self._load_file('trees.conf')
        self._load_file('testsets.conf')
        self._load_file('metrics.conf')
        machinedir = os.path.join(settings.CONFIG_ROOT, 'machines')
        if os.path.exists(machinedir):
            for f in os.listdir(machinedir):
                if f.endswith('.conf'):
                    self._load_file(os.path.join('machines', f))

        # Error messages are confusing if we don't validate in order
        for cls in ['Partition', 'Target']:
            if not cls in self.objects:
                continue
            objs = self.objects[cls]
            bad_names = []
            for name in objs:
                obj = objs[name]
                error = obj._finish(self)
                if error != None:
                    self._add_error(obj.filename, obj.section, error)
                    bad_names.append(name)
            for name in bad_names:
                del objs[name]

class ConfigObject(object):
    name_pattern = r'[a-zA-Z][a-zA-Z0-9_.-]+'

    @classmethod
    def get(cls, name):
        return settings.CONFIG.objects[cls.__name__][name]

    @classmethod
    def all(cls):
        try:
            return settings.CONFIG.objects[cls.__name__].values()
        except KeyError:
            return []

    def __repr__(self):
        return self.__class__.__name__ + '(' + self.name + ')'

class Machine(ConfigObject):
    def _load(self, parser, section):
        self.owner = parser.get(section, 'owner')
        self.location = parser.get(section, 'location')
        self.summary = parser.get(section, 'summary')
        self.cpu = parser.get(section, 'cpu')
        self.graphics = parser.get(section, 'graphics')
        self.memory = parser.get(section, 'memory')

class Metric(ConfigObject):
    def _load(self, parser, section):
        self.description = parser.get(section, 'description')
        self.units = parser.get(section, 'units')

class Partition(ConfigObject):
    name_pattern = r'(?P<_machine>[a-zA-Z][a-zA-Z0-9_.-]+)/[a-zA-Z][a-zA-Z0-9_.-]+'

    def _load(self, parser, section):
        self.disk = parser.get(section, 'disk')
        self.filesystem = parser.get(section, 'filesystem')

    def _finish(self, config):
        try:
            self.machine = config.objects['Machine'][self._machine]
            self.short_name = self.name[len(self.machine.name) + 1:]
        except KeyError, e:
            return "No machine named %s" % self._machine

class Target(ConfigObject):
    name_pattern = r'(?P<_partition>[a-zA-Z][a-zA-Z0-9_.-]+/[a-zA-Z][a-zA-Z0-9_.-]+)/(?P<_tree>[a-zA-Z][a-zA-Z0-9_.-]+)/(?P<_testset>[a-zA-Z][a-zA-Z0-9_.-]+)'

    def _load(self, parser, section):
        self.name = section[len('target '):]

    def _finish(self, config):
        try:
            self.partition = config.objects['Partition'][self._partition]
        except KeyError, e:
            return "No partition named %s" % self._partition
        try:
            self.tree = config.objects['Tree'][self._tree]
        except KeyError, e:
            return "No tree named %s" % self._tree
        try:
            self.testset = config.objects['TestSet'][self._testset]
        except KeyError, e:
            return "No testset named %s" % self._testset

class TestSet(ConfigObject):
    def _load(self, parser, section):
        self.description = parser.get(section, 'description')

class Tree(ConfigObject):
    def _load(self, parser, section):
        self.path = parser.get(section, 'path')
        self.description = parser.get(section, 'description')
