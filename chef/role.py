from chef.base import ChefObject, ChefObjectAttributes

class Role(ChefObject):
    """A Chef role object."""

    url = '/roles'
    attributes = {
        'description': str,
        'run_list': list,
        'default_attributes': ChefObjectAttributes,
        'override_attributes': ChefObjectAttributes,
        'env_run_lists': dict
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
            data['default_attributes'] = {}
        super(Role, self)._populate(data)
        self.attributes = ChefObjectAttributes((data.get('default_attributes', {}),
                                          data.get('override_attributes', {})), write=data['default_attributes'])
