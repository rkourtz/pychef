import abc
from chef.base import ChefObject, ChefObjectAttributes
from chef.exceptions import ChefError
      
class Environment(ChefObject):
    """A Chef environment object.

    .. versionadded:: 0.2
    """

    url = '/environments'
    
    api_version = '0.10'

    attributes = {
        'description': str,
        'cookbook_versions': dict,
        'default_attributes': ChefObjectAttributes,
        'override_attributes': ChefObjectAttributes
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
        data['default_attributes'] = {}
      super(Environment, self)._populate(data)
      self.attributes = ChefObjectAttributes((data.get('default_attributes', {}),
                                          data.get('override_attributes', {})), write=data['default_attributes'])
    
