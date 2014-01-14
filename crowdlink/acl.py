import yaml
from . import root

from lever import build_acl


acl_yaml = yaml.load(open(root + '/crowdlink/acl.yaml'))
acl = build_acl(acl_yaml)
