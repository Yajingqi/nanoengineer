"""
$Id$
"""

#e stub, nim

# biggest nim issues [some marked with ####]:
# - where to put a caching map from kidnode, args to MT(kidnode, args)
#   - note, that's a general issue for any "external data editor"
#     where the node is the external data and MT is our preferred-edit-method
#   - does the scheme used for _texture_holder make sense? ###k
#     - should the usual place for maps like this be explicit MemoDicts located in self.env?? ###k
#       by "like this" I mean, maps from objects to fancier things used to interface to them, potentially shared.
#     - how similar is this to the map by a ColumnList from a kid fixed_type_instance to CLE(that instance)?
#       - guess: it can be identical if we specify what ought to be included in the map-key, i.e. when to share.
#         If that includes "my ipath" or "my serno" (my = the instance), it can act like a local dict (except for weakref issues).
# - where & how to register class MT as the "default ModelTree viewer for Node",
#   where 'ModelTree' is basically a general style or place of viewing, and Node is a type of data the user might need to view that way?
#   And in viewing a kid (inside this class), do we go through that central system to create the viewer for it, passing it enough env
#   that it's likely to choose the same MT class to view a kid of a node and that node, but not making this unavoidable? [guess: yes. ##k]
#   Note: if so, this has a lot to say about the viewer-caching question mentioned above.
#   Note: one benefit of that central system is to help with handling other requests for an "obj -> open view of it" map,
#    like for cross-highlighting, or to implem "get me either an existing or new ModelTree viewer for this obj, existing preferred".
#    These need a more explicit ref from any obj to its open viewers than just their presumed observer-dependency provides.
#    Note that the key might be more general for some purposes than others, e.g. I'll take an existing viewer even if it was opened
#    using prefs different than I'd use to make a new one. I'm not sure if any one cache needs more than one key-scheme applicable to
#    one value-slot. Let's try to avoid that for now, except for not excluding it in the general architecture of the APIs.
# - arg semantics for Node
# - or for time-varying node.kids (can be ignored for now)

# complicated details:
# - usage/mod tracking of node.open, node.kids
#   [maybe best to redo node, or use a proxy... in future all model objs need this natively]
#   - for an initial demo, do it read-only, i.e. don't bother tracking changes by others to external state

# needed polish:
# - better fonts - from screenshots of NE1 or Safari?
#   - appearing selected
#   - italic, for disabled
# - current-part indicator
# - transparency

# opportunities for new features:
# - cross-highlighting -- mouseover an atom, chunk, jig, or MT chunk or jig, highlights the others too, differently
#   - does require realtime changetracking, *but* could be demoed on entirely new data rather than Node,
#    *or* could justify adding new specialcase tracking code into Node, Atom, Bond.

# small nims:
# - map_Expr
# - mt_instance = MT(obj) # with arg1 being already instantiated, this should make an instance ###IMPLEM that #k first be sure it's right

# #e more??

from basic import *
from basic import _self

from ToggleShow import * # e.g. If, various other imports we should do explicitly #e

If = If_kluge ####e until it works, then remove and retest

Node = Stub

# == trivial prototype of central cache of MT-viewers for objects

def _make_new_MT_viewer_for_object(key):
    obj, essential_data = key
    # obj is a Node or equivalent
    mt_instance = MT(obj) # but will this work, with arg1 being already instantiated -- will it make an instance? not yet! ###IMPLEM that
    return mt_instance

_MT_viewer_for_object = MemoDict(_make_new_MT_viewer_for_object)
    # args are (object, essential-data) where data diffs should prevent sharing of an existing viewer
    # (this scheme means we'd find an existing but not now drawn viewer... but we only have one place to draw one at a time,
    #  so that won't come up as a problem for now.)
    # (this is reminiscent of the Qt3MT node -> TreeItem map...
    #  will it have similar problems? I doubt it, except a memory leak at first, solvable someday by a weak-key node,
    #  and a two-level dict, key1 = weak node, key2 = essentialdata.)

def MT_viewer_for_object(obj, essential_data = None):
    return _MT_viewer_for_object( (obj, essential_data) ) # assume essential_data is already hashable (eg not dict but sorted items of one)

# ==

class MT(InstanceMacro):
    # compare to ToggleShow - lots of copied code

    # args
    node = Arg(Node) #### type?

    # state refs
    open ####
    
    # other formulae
    open_icon   = Overlay(Rect(0.4), TextRect('+',1,1))
    closed_icon = Overlay(Rect(0.4), TextRect('-',1,1))
    openclose_spacer = Spacer(0.4)
        #e or Invisible(open_icon); otoh that's no simpler, since open_icon & closed_icon have to be same size anyway
    
    openclose_visible = Highlightable( If( open, open_icon, closed_icon ), on_press = _self.toggle_open )
    
    def toggle_open(self):
        pass####
    
    openclose_slot = If( node.openable, openclose_visible, openclose_spacer )

    icon = Rect(0.4, 0.4, green)##stub; btw, would be easy to make color show hiddenness or type, bfr real icons work
        ###k is this a shared instance (multiply drawn)?? any issue re highlighting? need to "instantiate again"?
            ##e Better, this ref should not instantiate, only eval, once we comprehensively fix instantiation semantics.
            # wait, why did I think "multiply drawn"? it's not. nevermind.
        ##e selection behavior too
    label = TextRect( node.name ) ###e will need revision to Node or proxy for it, so node.name is usage/mod-tracked
        ##e selection behavior too --
        #e probably not in these items but in the surrounding Row (incl invis bg? maybe not, in case model appears behind it!)
        ##e italic for disabled nodes
        ##e support cmenu
    
    _value = SimpleRow(
        openclose_slot,
        SimpleColumn(
            SimpleRow(icon, label),
            If( open,
                      MT_kids(node.kids), ###e implem or find kids... needs usage/mod tracking
                      Spacer(0) ###BUG that None doesn't work here: see comment in ToggleShow.py
                      )
        )
    )
    pass

class MT_kids(InstanceMacro):
    # args
    kids = Arg(list_Expr)####k more like List or list or Anything...
        ##### note: the kid-list itself is time-varying (not just its members); need to think thru instantiation behavior;
        # what we want in the end is to cache (somewhere, not sure if in _self)
        # the mapping from the kid instance (after If eval - that eval to fixed type thing like in Column, still nim)
        # to the MT instance made from that kid. We would cache these with keys being all the args... like for texture_holder.
        # so that's coarser grained caching than if we did it in _self, but finer than if we ignored poss of varying other args
        # (btw do i mean args, or arg-formulae??).

        # note that the caching gets done in here as we scan the kids... *this* instance is fixed for a given node.kids passed to it.
        # BTW maybe our arg should just be the node, probably that's simpler & better,
        # otoh i ought to at least know how it'd work with arg being node.kids which timevaries.

    _value = Column( map_Expr( MT_viewer_for_object, kids )) ###e change to caching map?? no, MT_viewer_for_object does the caching.
        #e needs Column which takes a time-varying list arg
        #e change to ScrollableColumn someday (also resizable, scrolling kicks in when too tall; how do we pick threshhold? fixed at 10?)
    pass

