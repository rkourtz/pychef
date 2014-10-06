from chef.base import ChefObject, ChefObjectAttributes
from chef.exceptions import ChefError

class Node(ChefObject):
    """A Chef node object.

    The Node object can be used as a dict-like object directly, as an alias for
    the :attr:`.attributes` data::

        >>> node = Node('name')
        >>> node['apache']['log_dir']
        '/var/log/apache2'

    .. versionadded:: 0.1

    .. attribute:: attributes

        :class:`~chef.node.ChefObjectAttributes` corresponding to the composite of all
        precedence levels. This only uses the stored data on the Chef server,
        it does not merge in attributes from roles or environments on its own.

        ::

            >>> node.attributes['apache']['log_dir']
            '/var/log/apache2'

    .. attribute:: run_list

        The run list of the node. This is the unexpanded list in ``type[name]``
        format.

        ::

            >>> node.run_list
            ['role[base]', 'role[app]', 'recipe[web]']

    .. attribute:: chef_environment

        The name of the Chef :class:`~chef.Environment` this node is a member
        of. This value will still be present, even if communicating with a Chef
        0.9 server, but will be ignored.

        .. versionadded:: 0.2

    .. attribute:: default

        :class:`~chef.node.ChefObjectAttributes` corresponding to the ``default``
        precedence level.

    .. attribute:: normal

        :class:`~chef.node.ChefObjectAttributes` corresponding to the ``normal``
        precedence level.

    .. attribute:: override

        :class:`~chef.node.ChefObjectAttributes` corresponding to the ``override``
        precedence level.

    .. attribute:: automatic

        :class:`~chef.node.ChefObjectAttributes` corresponding to the ``automatic``
        precedence level.
    """

    url = '/nodes'
    attributes = {
        'default': ChefObjectAttributes,
        'normal': lambda d: ChefObjectAttributes(d, write=d),
        'override': ChefObjectAttributes,
        'automatic': ChefObjectAttributes,
        'run_list': list,
        'chef_environment': str
    }

    def has_key(self, key):
      return self.attributes.has_dotted(key)

    def get(self, key, default=None):
        return self.attributes.get(key, default)

    def __getitem__(self, key):
        return self.attributes[key]

    def __setitem__(self, key, value):
        self.attributes[key] = value

    def _populate(self, data):
        if not self.exists:
            # Make this exist so the normal<->attributes cross-link will
            # function correctly
            data['normal'] = {}
        data.setdefault('chef_environment', '_default')
        super(Node, self)._populate(data)
        self.attributes = ChefObjectAttributes((data.get('automatic', {}),
                                          data.get('override', {}),
                                          data['normal'], # Must exist, see above
                                          data.get('default', {})), write=data['normal'])

    def cookbooks(self, api=None):
        api = api or self.api
        return api[self.url + '/cookbooks']
