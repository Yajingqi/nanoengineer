# Copyright (c) 2005 Nanorex, Inc.  All rights reserved.
"""
moviefile.py -- classes and other code for interpreting movie files
(of various formats, once we have them)

$Id$
"""
__author__ = "Bruce" #k for now... I might bring in some older code too

# note that in future there's more than one class, and a function to figure out the right one to use
# for an existing file, or to be told this (being told the format) for a new file we'll cause to be made...
#
# so the external code should rarely know the actual classnames in this file!

# these imports are anticipated, perhaps not all needed
import os, sys
from struct import unpack
from VQT import A
import platform
from debug import print_compact_stack, print_compact_traceback


##e should rename this (see comment higher up for why)
class MovieFile: #bruce 050426 
    """Know the filename and format of an existing moviefile, and enough about it to read requested frames from it
    and report absolute atom positions (even if those frames, or all frames in the file, are differential frames).
       Provide methods for renaming it (actually moving or copying the file), when this is safe.
       Sometimes keep it open with a known file pointer, for speed.
       Sometimes keep cached arrays of absolute positions (like key frames but perhaps computed rather than taken from the file),
    either for speed or since it's the only way to derive absolute positions from delta frames in the file.
       [#e Someday we'll work even on files that are still growing, but this probably won't be tried for Alpha5.]
       What we *don't* know includes: anything about the actual atoms (if any) being repositioned as this file is read;
    anything about associated files (like a tracefile) or sim run parameters (if any), except whatever might be needed
    to do our job of interpreting the one actual moviefile we know about.
       Possible generalizations: really we're one kind of "atom-set trajectory", and in future there might be other kinds
    which don't get their data from files. (E.g. an object to morph atom-set-positions smoothly between two endpoints.)
    """
    ##e How to extend this class to the new movie file format:
    # split it into one superclass with the toplevel caching-logic,
    # and two subclasses (one per file format) with the lower-level skills
    # specific to how often those files contain key frames (never vs. regularly),
    # and their other differences. But note that this obj's job is not really to interpret
    # the general parts of the new-format file header, only the "trajectory part".
    # So probably some other object would parse the header and only then hand off the rest of the file
    # to one of these.
    def __init__(self, filename):
        self.filename = filename
        # conceivably the file does not yet exist and this is not an error
        # (if we're being used on a still-growing file whose producer didn't quite start writing it yet),
        # so let's check these things as needed/requested rather than on init.
        # For now we'll just "know that we don't know them".
        # This might be best done using __getattr__... and perhaps some quantities
        # are different each time we look (like file length)... not yet decided.

        # But does the caller need to tell us the set of starting atom positions,
        # in case the file doesn't? What if it doesn't know (for new-format file being explored)? ###e
        # ... the way it tells us is by calling donate_immutable_cached_frame if it needs to,
        # on any single frame it wants (often but not always frame 0).

        self.temp_mutable_frames = {}
        self.cached_immutable_frames = {} #e for some callers, store a cached frame 0 here

    ###e stuff for file header, natoms, format, size, etc, goes here; some of it is told to our init, not derived here.

    def frame_index_in_range(n):
        assert type(n) == type(1)
        return n >= 0 #####stub

    def ref_to_transient_frame_n(self, n):
        """[This is meant to be the main external method for retrieving our atom positions,
            when the caller cares about speed but doesn't need to keep this array
            (e.g. when it's playing us as a movie).]
        Return a Numeric array containing the absolute atom positions for frame n.
        Caller promises not to modify this array, and to never use it again after
        the next time anything calls any(??) method of this object. (Since we might
        keep modifying and returning the same mutable array, each time this method
        is called for the next n during a scan.)
           [#e Someday we might need to document some methods that are safe to call even while
        the caller still wants to use this array, and/or provide a scheme by which the
        caller can ask whether it's holding of that array remains valid or not -- note that
        several callers might have "different holdings of the same physical array" for which
        that answer differs. Note that a "copy on write" scheme (an alternative to much of this)
        might be better in the long run, but I'm not sure it's practical for Numeric arrays,
        or for advising self on which frames to keep and which to discard.
        """
        res = self.copy_of_frame(n) # res is owned by this method-run...
        self.donate_mutable_known_frame(n, res) # ... but not anymore!
            # But since we're a private implem, we can depend on res still
            # being valid and constant right now, and until the next method
            # on self is called sometime after we return.
        return res
    
    def copy_of_frame(self, n):
        """Return the array of absolute atom positions corresponding to
        the specified frame-number (0 = array of initial positions).
        If necessary, scan through the file as needed (from a key frame, in future format,
        or from the position of a frame whose abs posns we have cached, in old format)
        in order to figure this out.
        """
        assert self.frame_index_in_range(n)
        n0 = self.nearest_knownposns_frame_index(n)
        frame0 = self.copy_of_known_frame_or_None(n0) # an array of absposns we're allowed to modify, valid for n0
        assert frame0 != None # don't test it as a boolean -- it might be all 0.0 which in Numeric means it's false!
        while n0 < n:
            # move forwards using a delta frame (which is never cached, tho this code doesn't need to know that)
            # (##e btw it might be faster to read several at once and combine them into one, or add all at once, using Numeric ops!
            #  I'm not sure, since intermediate states would use 4x the memory, so we might do smaller pieces at a time...)
            n0 += 1
            df = self.delta_frame(n0) # array of differences to add to frame n0-1 to get frame n0
            frame0 += df # note: += modifies frame0 in place (if it's a Numeric array, as we hope); that's desired
        while n0 > n:
            # (this never happens if we just moved forwards, but there's no need to "confirm" or "enforce" that fact)
            # move backwards using a delta frame
            # (btw it might be faster to read all dfs forwards to make one big one to subtract all at once...
            #  or perhaps even to read them all at once into a single Numeric 2d array, and turn them into
            #  one big one using Numeric ops! ###e)
            df = self.delta_frame(n0)
            n0 -= 1 # note: we did this after grabbing the frame, not beforehand as above
            frame0 -= df
        #e future:
        #e   If we'd especially like to keep a cached copy for future speed, make one now...
        #e   Or do this inside forward-going loop?
        #e   Or in caller, having it stop for breath every so many frames, perhaps also to process user events?
        return frame0

    def donate_mutable_known_frame(self, n, frame):
        """Caller has a frame of absolute atom positions it no longer needs --
        add this to our cache of known frames, marked as able to be modified further as needed
        (i.e. as its data not needing to be retained in self after it's next returned by copy_of_known_frame_or_None).
        This optimizes serial scans of the file, since the donated frame tends to be one frame away
        from the next desired frame.
        """
        self.temp_mutable_frames[n] = frame
            # it's probably ok if we already had one for the same n and this discards it --
            # we don't really need more than one per n
        ###e do something to affect the retval of nearest_knownposns_frame_index?? it should optimize for the last one of these being near...
        return

    def donate_immutable_cached_frame(self, n, frame):
        """Caller gives us the frame of abs positions for frame-index n,
        which we can keep and will never modify (in case caller wants to keep using it too),
        and caller also promises to never modify it (so we can keep trusting and copying it).
        This is the only way for client code using us on an all-differential file
        can tell us a known absolute frame from which other absolute frames can be derived.
        Note that that known frame need not be frame 0, and perhaps will sometimes not be
        (I don't know, as of 050426 2pm).
        """
        self.cached_immutable_frames[n] = frame
            # note: we only need one per n! so don't worry if this replaces an older one.
        ###e do something to affect the retval of nearest_knownposns_frame_index??
        return
    
    def copy_of_known_frame_or_None(self, n):
        """If we have a mutable known frame at index n, return it
        (and forget it internally since caller is allowed to modify it).
        If not, we should have an immutable one, or the file should have one (i.e. a key frame).
        Make a copy and return it.
        If we can't, return None (for some callers this will be an error; detecting it is up to them).
        """
        try:
            return self.temp_mutable_frames.pop(n)
        except KeyError:
            try:
                #e we don't yet support files with key frames, so a cached one is our only chance.
                frame_notouch = self.cached_immutable_frames[n]
            except KeyError:
                return None
            else:
                return + frame_notouch # the unary "+" makes a copy (since it's a Numeric array)
        pass

    def nearest_knownposns_frame_index(self, n):
        """Figure out and return n0, the nearest frame index to n
        for which we already know the absolute positions, either since it's a key frame in the file
        or since we've kept a cached copy of the positions (or been given those positions by our client code) --
        either a mutable copy or an immutable one.
        (This index is suitable for passing to copy_of_known_frame_or_None, but that method might or might not
         have to actually copy anything in order to come up with a mutable frame to return.)
           By "nearest", we really mean "fastest to scan over the delta frames from n0 to n",
        so if scanning forwards is faster then we should be biased towards returning n0 < n,
        but this issue is ignored for now (and will become barely relevant once we use the new file format
        with frequent occurrence of key frames).
           It's not an error if n is out of range, but the returned n0 will always be in range.
           If we can't find *any* known frame, return None (but for most callers this will be an error). ###e better to asfail??
        """
        # It's common during sequential movie playing that the frame we want is 1 away from what we have...
        # so it's worth testing this quickly, at least for the mutable frames used during that process.
        # (In fact, this is probably more common than an exact match! So we test it first.)
        if n - 1 in self.temp_mutable_frames:
            return n - 1
        if n + 1 in self.temp_mutable_frames:
            return n + 1
        # It's also common than n is already known, so test that quickly too.
        if n in self.temp_mutable_frames or n in self.cached_immutable_frames:
            return n
        # No exact match. In present code, we won't have very many known frames,
        # so it's ok to just scan them all and find the one that's actually nearest.
        # (For future moviefile format with frequent key frames, we'll revise this quite a bit.)
        max_lower = too_low = -1
        min_higher = too_high = 100000000000000000000000 # higher than any actual frame number (I hope!)
        for n0 in self.temp_mutable_frames.keys() + self.cached_immutable_frames.keys():
            if n0 < n:
                max_lower = max( max_lower, n0)
            else:
                min_higher = min( min_higher, n0)
        if max_lower > too_low and min_higher != too_high:
            # which is best: scanning forwards by n - max_lower, or scanning backwards by min_higher - n ?
            if n - max_lower <= min_higher - n:
                return max_lower
            else:
                return min_higher
        elif max_lower > too_low:
            return max_lower
        elif min_higher != too_high:
            return min_higher
        else:
            assert 0, "no known frame!" # for now, since I think this should never happen (unless file of new format is very incomplete)
            return None
        pass

    pass # end of class MovieFile

