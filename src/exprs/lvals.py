'''
lvals.py - various kinds of "lvalue" objects (slots for holding attribute values)
with special behavior such as usage-tracking and invalidation/update.

$Id$
'''

from basic import *

# ==

class Lval: ####@@@@ most inval behavior is nim; it needs to be integrated with the env.prefs usage tracking in changes.py
    """Lval(formula) -> standard lval for that formula, has .get_value(), .set_formula,
    does inval flag/subs/propogate, tracks own usage
    """
    valid = False
    def __init__(self, formula = None):
        """For now, formula is either None (meaning no formula is set yet -- error to use),
        or any callable [WRONG i think] [?? or thing taking compute_value method?? ####]
        which does usage-tracking of whatever it uses into its dynenv in the standard way,
        and returns its value (perhaps None or another callable, treated as any other value).
        Note that unlike InvalMixin _recompute_ methods, it can't work by setting the value instead.
           In future, other special kinds of formulas might be permitted, and used differently.
           [WARNING: if we try to generalize by letting formula be a python value used as a constant,
        we'll have an ambiguity if that value happens to be callable, so we'd need a ConstantFormula constructor instead --
        or fix this by not passing a callable, but a Formula object with a compute_value method,
        and having a way to make one of those from a callable, when desired, and change the client call of Lval(compute_method). ###e]
        """
        self._usage_record = {} # or use begin_tracking_usage??
        self.set_formula(formula)
    def set_formula(self, formula):
        self._formula = formula
        self.inval() ###e only if different??
    def inval(self):
        if self.valid:
            self.valid = False
            ###e then propogate, but only if we were valid before this, I think
    def get_value(self):
        if not self.valid:
            self._value = self._C_value()
            self.valid = True
        ###e do standard usage tracking into env -- compatible with env.prefs
            # (i forget if the needed bugfix in changes.py for propogating invals applies to that)
        return self._value
    def _C_value(self):
        """compute our value, tracking what it uses, subscribing our inval method to that.
        NOTE: does not yet handle diffing of prior values of what was used, or the "tracking in order" needed for that.
        Maybe a sister class (another kind of Lval) will do that.
        """
        #e handle various kinds of formulas, or objs that should be coerced into them -- make_formula(formula_arg)?
        assert self._formula is not None, "our formula is not yet set: %r" % self
        self._usage_record.clear() #k needed?
        val = self._formula.get_value( self._usage_record) ###e who checks for exceptions in this, it or us? it does.
        ###@@@e subscribe self.inval to members of self._usage_record
        #e optim (finalize) if that's empty (only if set_formula or direct inval won't be called; how do we know?)
        return val
    pass

def LvalDict(wayfunc, lvalclass = Lval): #e option to not memoize for certain types of keys (like trivials or errors)?? this or Memo?
    """An extensible dict of lvals of the given lval class, whose memoized values will be recomputed from dict key using wayfunc(key)().
    It's an error (reported #nim in MemoDict) for computation of wk = wayfunc(key) to use any external usage-tracked lvalues,
    but it's ok if wk() does; subsequent inval of those lvals causes the lval created here to recompute and memoize wk() on demand.
    This is more useful than if the entire dict had to be recomputed (i.e. if a _C_ rule told how to recompute the whole thing),
    since only the specific items that become invalid need to be.
       Design note: DO WE RETURN THE LVALS or their values??
    For now, WE RETURN THE LVALS (partly since implem is easier, partly since it's more generally useful);
    this might be less convenient for the user.
    """
    #k Note:
    # I'm only 90% sure the "wayfunc = wayfunc, lvalclass = lvalclass" lambda closure kluge is still needed in Python, in this case.
    # I know it's needed in some cases, but maybe only when they are variables??
    # More likely, whenever the lambda is used outside their usual scope, as it is in this case.
    return MemoDict( lambda key, wayfunc = wayfunc, lvalclass = lvalclass:
                     lvalclass( FormulaFromCallable( wayfunc(key))) )

def LvalDict2(valfunc, lvalclass = Lval):
    """Like LvalDict but uses a different recompute-function API, which might be easier for most callers to supply;
    if it's always better, it'll replace LvalDict.
    In this variant, just pass valfunc, which will be applied to key in order to recompute the value at key.
    """
    return MemoDict( lambda key, valfunc = valfunc, lvalclass = lvalclass:
                     lvalclass( FormulaFromCallable( lambda valfunc=valfunc, key=key: valfunc(key))) )

# ==

class InvalidatableAttrsMixin(object): # object superclass is needed, to make this a new-style class, so a python property will work.
    """Mixin class, for supporting "standard compute methods" in any client class.
    We support two kinds of compute methods:
    - _C_xxx methods, for recomputing values of individual attrs like self.xxx;
    - pairs of _CK_xxx and _CV_xxx methods, for recomputing the set of keys, and individual values, within dictlike attrs self.xxx.
    [Details to be explained. Features to be added: let client determine lval classes.]
    WARNING: entirely NIM or buggy as of 061020.
    """
    def __getattr__(self, attr):
        # return quickly for attrs that can't have compute rules
        if attr.startswith('__') or attr.startswith('_C'):
            raise AttributeError, attr # must be fast for __repr__, __eq__, __add__, etc
            # Notes:
            # - We only catch __xx here, not _xx, since _xx is permitted to have compute rules, e.g. _C__xx.
            #   Btw, __xx will only exist if it's really __xx__, since otherwise it would be name-mangled to _<classname>__xx.
            # - We exclude _Cxx so that no one tries to define a compute rule for a compute rule (hard to support, not very useful).

        # look for a compute method for attr, either _C_attr (used alone) or _CK_attr and/or _CV_attr (used together),
        # in self.__class__; if found, create and save a property in the class (so this only happens once per attr and class).
        # (#e should we grab the prefix out of the rule constructor, since it needs to know it anyway?)
        if _compile_compute_rule( self.__class__, attr, '_C_', _C_rule ) or \
           _compile_compute_rule( self.__class__, attr, '_CV_', _CV_rule ): # also incorporates _CK_ for same attr, if it exists
            # One of the above calls of _compile_compute_rule defined a property in self.__class__ for attr.
            # Use it now! [This will cause infrecur if the function said it's there and it's not! Fix sometime. #e]
            return getattr(self, attr)

        raise AttributeError, attr
    pass # end of class InvalidatableAttrsMixin

def _compile_compute_rule( clas, attr, prefix, propclass ):
    """[private helper function]
    Try to create a compute rule for accessing attr in clas (which needs to inherit from object for this to be possible),
    using a compute method named (prefix + attr) found in clas (if one is there).
       If you find that method, store a property (or similar object -- I forget the general name for them ###doc)
    implementing the compute rule in clas.attr, created by propclass(...), and return True. Otherwise return False.
    """
    assert isinstance( clas, object), "compute rules are only supported on new-style classes, not %r" % clas
    try:
        unbound_method = getattr( clas, prefix + attr)
    except AttributeError:
        return False
    assert callable(unbound_method), "prefix %r is reserved for use on compute methods, but .%s is not callable on %r" % \
           (prefix, prefix + attr, clas)
    prop = propclass( clas, attr, unbound_method, prefix ) # on error, this can raise an exception; or it can return None
    if prop is None:
        return False
    # assume prop is a suitable property object for use in a new-style class    
    setattr( clas, attr, prop)
    ###e improved design: propclass should instead be an object which can store a list of new properties (descriptors)
    # on a list of corresponding attrs;
    # that way it could know the prefixes itself, know how to look for the unbound methods,
    # and support the definition of more than one attr-descriptor, e.g. one for attr and one for associated values
    # like direct access to an LvalDict associated with a _CV_rule attr. When we need the latter, revise the design like that.
    return True

class _C_rule(object): ###e rename, since this is not a compute method? #e give it and _CV_rule a common superclass?
    "act like a property that implements a recompute rule using an Lval made from a _C_attr compute method"
    def __init__(self, clas, attr, unbound_method, prefix):
        assert prefix == '_C_' and unbound_method == getattr( clas, prefix + attr) # a sign of bad API design of _compile_compute_rule?
        #e store stuff
        self.attr = attr
        self.prefix = prefix
        return
    def __get__(self, instance, owner):
        if instance is None:
            # we're being accessed directly from class
            return self
        # find the Lval object for our attr in instance
        attr = self.attr
        try:
            lval = instance.__dict__[attr]
        except KeyError:
            # make a new Lval object from the compute_method (happens once per attr per instance)
            mname = self.prefix + attr
            compute_method = getattr(instance, mname) # should always work
            lval = instance.__dict__[attr] = Lval(FormulaFromCallable(compute_method))
        return lval.get_value() # this does usage tracking, validation-checking, recompute if needed
            # Notes:
            # - There's a reference cycle between compute_method and instance, which is a memory leak.
            # This could be fixed by using a special Lval (stored in self, not instance, but with data stored in instance)
            # which we'd pass instance to on each use. (Or maybe a good solution is a C-coded metaclass, for making instance?)
            # - The __set__ below detects the error of the compute method setting the attr itself. Good enough for now.
            # Someday, if we use a special Lval object that is passed self and enough into to notice that itself,
            # then we could permit compute objects to do that, if desired. But the motivation to permit that is low.
            # - There is no provision for direct access to the Lval object (e.g. to directly call its .set_formula method).
            # We could add one if needed, but I don't know the best way. Maybe find this property (self) and use a get_lval method,
            # which is passed the instance? Or, setattr(instance, '_lval_' + attr, lval).
    def __set__(self, instance, val):
        #e can instance be None here??
        assert 0, "not allowed to set attr %r in %r" % (self.attr, instance)
    #e could make __delete__ do an inval... should we?? ###
    pass # end of class _C_rule

class _CV_rule(object):
    """Act like a property that implements a per-item recompute rule for a dictlike object
    stored at instance.attr, using an LvalDict made from a _CV_attr compute method for item values,
    and an optional _CK_attr compute method for the complete list of keys.
       If the _CK_attr method is not present, the set of keys is undefined and the dictlike object
    (value of instance.attr) will not support iteration over keys, items, or values.
       Whether or not iteration is supported, direct access to the LvalDict is provided [how? ###e, nim],
    which makes it possible to iterate over the dict items created so far.
    """
    def __init__(self, clas, attr, unbound_method, prefix):
        assert prefix == '_CV_' and unbound_method == getattr( clas, prefixV + attr)
        self.attr = attr
        self.prefixV = prefix
        self.prefixK = '_CK_'
        self.has_CK = not not getattr( clas, prefixK + attr, False)
        return
    def __get__(self, instance, owner):
        if instance is None:
            # we're being accessed directly from class
            return self
        # find the RecomputableDict object for our attr in instance
        attr = self.attr
        try:
            obj = instance.__dict__[attr]
            print "warning: obj was not found directly, but it should have been, since this is a non-data descriptor", self #e more?
        except KeyError:
            # make a new object from the compute_methods (happens once per attr per instance) 
            compute_methodV = getattr(instance, self.prefixV + attr) # should always work
            compute_methodK = getattr(instance, self.prefixK + attr, None) # optional method
            obj = instance.__dict__[attr] = RecomputableDict(compute_methodV, compute_methodK)
        return obj
    # we have no __set__ method, so in theory, once we've stored obj in instance.__dict__ above, it will be gotten directly
    # without going through __get__. We print a warning above if that fails.

    # note: similar comments about memory leaks apply, as for _C_rule.
    
    pass # end of class _CV_rule

class DictFromKeysAndFunction(InvalidatableAttrsMixin): #e refile in py_utils? not sure -- recursive import problem re superclass?
    """Act like a read-only dict with a fixed set of keys (computed from a supplied function when first needed;
    if that func is not supplied, all keys are permitted and iteration over this dict is not supported),
    and with all values computed by another supplied function (not necessarily constant, thus not cached).
    """
    def __init__(self, compute_value_at_key, compute_key_sequence = None, validate_keys = False):
        self.compute_value_at_key = compute_value_at_key
        self.compute_key_sequence = compute_key_sequence # warning: might be None
        self.validate_keys = validate_keys
    def _C_key_sequence(self):
        # called at most once, when self.key_sequence is first accessed
        assert self.compute_key_sequence, "iteration not supported in %r, since compute_key_sequence was not supplied" % self
        return self.compute_key_sequence()
    def _C_key_set(self):
        return dict([(key,key) for key in self.key_sequence])
    def __getitem__(self, key):
        if self.validate_keys: #e [if this is usually False, it'd be possible to optim by skipping this check somehow]
            if not key in self.key_set:
                raise KeyError, key
        return self.compute_value_at_key(key) # not cached in self
    # dict methods, only supported when compute_key_sequence was supplied
    def keys(self):
        "note: unlike for an ordinary dict, this is ordered, if compute_key_sequence retval is ordered"
        return self.key_sequence
    iterkeys = keys
    def values(self):
        "note: unlike for an ordinary dict, this is ordered, if compute_key_sequence retval is ordered"
        compval = self.compute_value_at_key
        return map( compval, self.key_sequence )
    itervalues = values
    def items(self):
        "note: unlike for an ordinary dict, this is ordered, if compute_key_sequence retval is ordered"
        compval = self.compute_value_at_key
        return [(key, compval(key)) for key in self.key_sequence]
    iteritems = items
    pass # end of class DictFromKeysAndFunction

from idlelib.Delegator import Delegator

class RecomputableDict(Delegator):
    """Act like a read-only dict with variable (invalidatable/recomputable) values,
    and a fixed key sequence used only to support iteration
    (with iteration not supported if the key sequence compute function is not supplied).
       If validate_keys is True, every __getitem__ verifies the supplied key is in the specified key sequence.
       #e Someday, self.lvaldict might be a public attr -- not sure if this is needed;
    main use is "iterate over values defined so far".
    """
    def __init__(self, compute_methodV, compute_methodK = None, validate_keys = False):
        self.lvaldict = LvalDict2(compute_methodV)
        Delegator.__init__( self, DictFromKeysAndFunction( self.compute_value_at_key, compute_methodK, validate_keys = validate_keys))
        return
    def compute_value_at_key(self, key):
        return self.lvaldict[key].get_value()
    pass
        
# end
