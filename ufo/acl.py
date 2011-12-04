import struct
from ufo.utils import get_user_infos

ACL_EA_VERSION = 0x0002

ACL_XATTR = "system.posix_acl_access"

ACL_READ = 0x04
ACL_WRITE = 0x02
ACL_EXECUTE = 0x01

ACL_UNDEFINED_TAG = 0x0
ACL_USER_OBJ = 0x01
ACL_USER = 0x02
ACL_GROUP_OBJ = 0x04
ACL_GROUP = 0x08
ACL_MASK = 0x10
ACL_OTHER = 0x20

ACL_UNQUALIFIED = 2**32 - 1

acl_types = { ACL_UNDEFINED_TAG : "_undefined",
              ACL_USER_OBJ : "user",
              ACL_USER : "user",
              ACL_GROUP_OBJ : "group",
              ACL_GROUP : "group",
              ACL_MASK : "mask",
              ACL_OTHER : "other" }

nfs4_acl_types = { ACL_UNDEFINED_TAG : "_undefined",
                   ACL_USER_OBJ : "OWNER@",
                   ACL_USER : "user",
                   ACL_GROUP_OBJ : "GROUP@",
                   ACL_GROUP : "group",
                   ACL_MASK : "mask",
                   ACL_OTHER : "EVERYONE@" }

acl_perms = ( ( ACL_READ, "r" ),
              ( ACL_WRITE, "wa" ),
              ( ACL_EXECUTE, "x" ) )

json_perms = ( ( ACL_READ, "read" ),
               ( ACL_WRITE, "write" ),
               ( ACL_EXECUTE, "execute" ) )

class ACL(list):
    default_domain = "agorabox.org"

    def __init__(self, *args, **kw):
        super(list, self).__init__(args, kw)
        self.mode = kw.get("mode")

    def __repr__(self):
        return "\n".join(map(repr, self))

    def __contains__(self, ace):
        if isinstance(ace, ACE):
            return list.__contains__(self, ace)
        else:
            for _ace in self:
                if _ace.kind & ACL_USER and _ace.qualifier == ace:
                    return True
            return False

    def to_nfs4(self):
        s = ""
        for ace in self:
            if ace.kind != ACL_MASK:
                s += ace.to_nfs4() + "\n"
        return s

    @staticmethod
    def from_xattr(data):
        index = 4
        acl = ACL()
        while index < len(data):
            acl.append(ACE(*struct.unpack("HHI", data[index:index + 8])), False)
            index += 8
        return acl

    @staticmethod
    def from_json(obj, mode=0):
        acl = ACL(mode=mode)
        for ace in obj:
            acl.append(ACE.from_json(ace))
        acl.check()
        return acl

    @staticmethod
    def from_mode(mode):
        acl = ACL()
        acl.append(ACE(ACL_USER_OBJ,
                       (mode >> 6) & 0x7,
                       2**32 - 1), False)
        acl.append(ACE(ACL_GROUP_OBJ,
                       (mode >> 3) & 0x7,
                       2**32 - 1), False)
        acl.append(ACE(ACL_OTHER,
                       mode & 0x7,
                       2**32 - 1), False)
        return acl

    def get(self, kind):
        aces = filter(lambda ace: ace.kind == kind, self)
        if kind not in (ACL_USER, ACL_GROUP):
            return aces[0]
        return aces

    def check(self, complete=True):
        required = set([ ACL_USER_OBJ, ACL_GROUP_OBJ, ACL_OTHER ])
        if self.is_extended():
            required.add(ACL_MASK)
        for ace in self:
            if ace.kind in required:
                required.remove(ace.kind)
        if required:
            if complete:
                if required != set([ACL_MASK]):
                    if self.mode == None:
                        raise Exception("You need to specify a mode for an newly created extended attribute")
                    for ace in ACL.from_mode(self.mode):
                        if ace.kind in required:
                            self.append(ace, False)
                self.calc_mask()
                self.sort()
                return self.check(False)
            raise Exception("Invalid ACL, missing %s" % ",".join(map(lambda x: acl_types[x], required)))

    def sort(self):
        list.sort(self, lambda e1, e2: e1.kind - e2.kind)

    def to_xattr(self):
        self.sort()
        self.check()
        if len(self) == 0:
            return None
        s = struct.pack("I", ACL_EA_VERSION)
        for ace in self:
            s += struct.pack("HHI", ace.kind, ace._perms, ace._qualifier)
        return s

    def to_json(self):
        self.sort()
        self.check()
        if len(self) == 0:
            return None
        return map(ACE.to_json, [ ace for ace in self if ace.kind == ACL_USER ])

    def calc_mask(self):
        mask = None
        perms = 0
        for ace in self:
            if ace.kind in [ ACL_USER_OBJ, ACL_OTHER ]:
                continue
            elif ace.kind == ACL_MASK:
                mask = ace
            elif ace.kind in [ ACL_USER, ACL_GROUP_OBJ, ACL_GROUP ]:
                perms |= ace._perms
            else:
                raise Exception("Invalid ACE")

        if not mask:
            mask = ACE(ACL_MASK)
            self.append(mask, False)

        mask._perms = perms

        return mask

    def is_extended(self):
        for ace in self:
            if ace.kind in [ ACL_MASK, ACL_USER, ACL_GROUP ]:
                return True
        return False

    def append(self, ace, check=False):
        list.append(self, ace)
        if check:
            self.check(complete=True)

    def __eq__(self, acl):
        return repr(self) == repr(acl)

class ACE:
    def __init__(self, kind, perms=0, qualifier=ACL_UNQUALIFIED):
        self.kind = kind
        self._perms = perms
        self._qualifier = qualifier

    def __repr__(self):
        qualifier = ""
        if self._qualifier != (1 << 32) - 1:
            qualifier = get_user_infos(uid=self._qualifier)['login']

        return "%s:%s:%s" % (acl_types[self.kind], qualifier, self.perms)

    def to_nfs4(self):
        if self._qualifier != (1 << 32) - 1:
            qualifier = get_user_infos(uid=self._qualifier)['login'] + '@' + ACL.default_domain
        else:
            qualifier = nfs4_acl_types[self.kind]
        return "A::%s:%s" % (qualifier, self.nfs4_perms)

    def to_json(self):
        return dict(qualifier=self._qualifier,
                    privileges=self.json_perms)

    def __eq__(self, ace):
        return self.kind == ace.kind and self._perms == ace._perms and self._qualifier == ace._qualifier

    @staticmethod
    def from_string(s):
        kind, qualifier, perms = s.split(':')
        for key, value in acl_types.items():
            if value == kind or value[0] == kind:
                if key == ACL_USER_OBJ and qualifier:
                    key = ACL_USER
                    _qualifier = get_user_infos(login=qualifier)['uid']
                elif key == ACL_GROUP_OBJ and qualifier:
                     key = ACL_GROUP
                     _qualifier = 0
                else:
                     _qualifier = ACL_UNQUALIFIED
                _kind = key
                break
        _perms = ACE.perms_from_string(perms)
        return ACE(_kind, _perms, _qualifier)

    @staticmethod
    def from_json(ace):
        ace = ACE(ACL_USER, ACE.perms_from_json(ace['privileges']), ace['qualifier'])
        return ace

    @staticmethod
    def perms_from_string(perms):
        _perms = 0
        for perm in perms.lower():
            if perm == "-": continue
            for mask, format in acl_perms:
                if format == perm:
                    _perms |= mask
                    break
        return _perms

    @staticmethod
    def perms_from_json(perms):
        _perms = 0
        perms = set(perms)
        if "read" in perms:
            _perms |= ACL_READ
        if "write" in perms:
            _perms |= ACL_WRITE
        if "execute" in perms:
            _perms |= ACL_EXECUTE
        return _perms

    @property
    def qualifier(self):
        if self.kind & ACL_USER:
            return get_user_infos(uid=self._qualifier)['login']
        return ""

    @property
    def perms(self):
        perms = ""
        for perm, char in acl_perms:
            if self._perms & perm:
               perms += char
            else:
               perms += "-"
        return perms

    @property
    def nfs4_perms(self):
        perms = ""
        for perm, char in acl_perms:
            if self._perms & perm:
               perms += char
        return perms

    @property
    def json_perms(self):
        perms = []
        for perm, s in json_perms:
            if self._perms & perm:
               perms.append(s)
        return perms

