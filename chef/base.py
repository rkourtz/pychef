import collections

import pkg_resources

from chef.api import ChefAPI
from chef.exceptions import *

class ChefQuery(collections.Mapping):
    def __init__(self, obj_class, names, api):
        self.obj_class = obj_class
        self.names = names
        self.api = api

    def __len__(self):
        return len(self.names)

    def __contains__(self, key):
        return key in self.names

    def __iter__(self):
        return iter(self.names)

    def __getitem__(self, name):
        if name not in self:
            raise KeyError('%s not found'%name)
        return self.obj_class(name, api=self.api)


class ChefObjectMeta(type):
    def __init__(cls, name, bases, d):
        super(ChefObjectMeta, cls).__init__(name, bases, d)
        if name != 'ChefObject':
            ChefObject.types[name.lower()] = cls
        cls.api_version_parsed = pkg_resources.parse_version(cls.api_version)


class ChefObject(object):
    """A base class for Chef API objects."""

    __metaclass__ = ChefObjectMeta
    types = {}

    url = ''
    attributes = {}

    api_version = '0.9'

    def __init__(self, name, api=None, skip_load=False):
        self.name = name
        self.api = api or ChefAPI.get_global()
        self._check_api_version(self.api)

        self.url = self.__class__.url + '/' + self.name
        self.exists = False
        data = {}
        if not skip_load:
            try:
                data = self.api[self.url]
            except ChefServerNotFoundError:
                pass
            else:
                self.exists = True
        self._populate(data)

    def _populate(self, data):
        for name, cls in self.__class__.attributes.iteritems():
            if name in data:
                value = cls(data[name])
            else:
                value = cls()
            setattr(self, name, value)

    @classmethod
    def from_search(cls, data, api=None):
        obj = cls(data.get('name'), api=api, skip_load=True)
        obj.exists = True
        obj._populate(data)
        return obj

    @classmethod
    def list(cls, api=None):
        """Return a :class:`ChefQuery` with the available objects of this type.
        """
        api = api or ChefAPI.get_global()
        cls._check_api_version(api)
        names = [name for name, url in api[cls.url].iteritems()]
        return ChefQuery(cls, names, api)

    @classmethod
    def create(cls, name, api=None, **kwargs):
        """Create a new object of this type. Pass the initial value for any
        attributes as keyword arguments.
        """
        api = api or ChefAPI.get_global()
        cls._check_api_version(api)
        obj = cls(name, api, skip_load=True)
        for key, value in kwargs.iteritems():
            setattr(obj, key, value)
        api.api_request('POST', cls.url, data=obj)
        return obj

    def save(self, api=None):
        """Save this object to the server. If the object does not exist it
        will be created.
        """
        api = api or self.api
        try:
            api.api_request('PUT', self.url, data=self)
        except ChefServerNotFoundError, e:
            # If you get a 404 during a save, just create it instead
            # This mirrors the logic in the Chef code
            api.api_request('POST', self.__class__.url, data=self)

    def delete(self, api=None):
        """Delete this object from the server."""
        api = api or self.api
        api.api_request('DELETE', self.url)

    def to_dict(self):
        d = {
            'name': self.name,
            'json_class': 'Chef::'+self.__class__.__name__,
            'chef_type': self.__class__.__name__.lower(),
        }
        for attr in self.__class__.attributes.iterkeys():
            d[attr] = getattr(self, attr)
        return d

    def __str__(self):
        return self.name

    def __repr__(self):
        return '<%s %s>'%(type(self).__name__, self)

    @classmethod
    def _check_api_version(cls, api):
        # Don't enforce anything if api is None, since there is sometimes a
        # use for creating Chef objects without an API connection (just for
        # serialization perhaps).
        if api and cls.api_version_parsed > api.version_parsed:
            raise ChefAPIVersionError, "Class %s is not compatible with API version %s" % (cls.__name__, api.version)

class ChefObjectAttributes(collections.MutableMapping):
    """A collection of Chef Object attributes.

    Attributes can be accessed like a normal python :class:`dict`::

        print environment['fqdn']
        environment['apache']['log_dir'] = '/srv/log'

    When writing to new attributes, any dicts required in the hierarchy are
    created automatically.

    .. versionadded:: 0.1
    """

    def __init__(self, search_path=[], path=None, write=None):
        if not isinstance(search_path, collections.Sequence):
            search_path = [search_path]
        self.search_path = search_path
        self.path = path or ()
        self.write = write

    def __iter__(self):
        keys = set()
        for d in self.search_path:
            keys |= set(d.iterkeys())
        return iter(keys)

    def __len__(self):
        l = 0
        for key in self:
            l += 1
        return l

    def __getitem__(self, key):
        for d in self.search_path:
            if key in d:
                value = d[key]
                break
        else:
            raise KeyError(key)
        if not isinstance(value, dict):
            return value
        new_search_path = []
        for d in self.search_path:
            new_d = d.get(key, {})
            if not isinstance(new_d, dict):
                # Structural mismatch
                new_d = {}
            new_search_path.append(new_d)
        return self.__class__(new_search_path, self.path+(key,), write=self.write)

    def __setitem__(self, key, value):
        if self.write is None:
            raise ChefError('This attribute is not writable')
        dest = self.write
        for path_key in self.path:
            dest = dest.setdefault(path_key, {})
        dest[key] = value

    def __delitem__(self, key):
        if self.write is None:
            raise ChefError('This attribute is not writable')
        dest = self.write
        for path_key in self.path:
            dest = dest.setdefault(path_key, {})
        del dest[key]

    def has_dotted(self, key):
        """Check if a given dotted key path is present. See :meth:`.get_dotted`
        for more information on dotted paths.

        .. versionadded:: 0.2
        """
        try:
            self.get_dotted(key)
        except KeyError:
            return False
        else:
            return True

    def get_dotted(self, key):
        """Retrieve an attribute using a dotted key path. A dotted path
        is a string of the form `'foo.bar.baz'`, with each `.` separating
        hierarcy levels.

        Example::

            environment.attributes['apache']['log_dir'] = '/srv/log'
            print environment.attributes.get_dotted('apache.log_dir')
        """
        value = self
        for k in key.split('.'):
            if not isinstance(value, ChefObjectAttributes):
                raise KeyError(key)
            value = value[k]
        return value

    def set_dotted(self, key, value):
        """Set an attribute using a dotted key path. See :meth:`.get_dotted`
        for more information on dotted paths.

        Example::

            environment.attributes.set_dotted('apache.log_dir', '/srv/log')
        """
        dest = self
        keys = key.split('.')
        last_key = keys.pop()
        for k in keys:
            if k not in dest:
                dest[k] = {}
            dest = dest[k]
            if not isinstance(dest, ChefObjectAttributes):
                raise ChefError
        dest[last_key] = value

    def to_dict(self):
        merged = {}
        for d in reversed(self.search_path):
            merged.update(d)
        return merged