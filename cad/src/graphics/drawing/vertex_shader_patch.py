"""
OpenGL extension ARB.vertex_shader

$Id$

This module customises the behaviour of the 
OpenGL.raw.GL.ARB.vertex_shader to provide a more 
Python-friendly API

### /Library/Python/2.5/site-packages/PyOpenGL-3.0.0b3-py2.5.egg/OpenGL/GL/ARB/vertex_shader.py
"""
from OpenGL import platform, constants, constant, arrays
from OpenGL import extensions, wrapper
from OpenGL.GL import glget
import ctypes
from OpenGL.raw.GL.ARB.vertex_shader import *

from shader_objects_patch import glGetObjectParameterivARB ### Added _patch.

base_glGetActiveAttribARB = glGetActiveAttribARB
def glGetActiveAttribARB(program, index):
    """
    Retrieve the name, size and type of the uniform of the index in the program
    """
    max_index = int(glGetObjectParameterivARB( program, GL_OBJECT_ACTIVE_ATTRIBUTES_ARB ))
    length = int(glGetObjectParameterivARB( program, GL_OBJECT_ACTIVE_ATTRIBUTE_MAX_LENGTH_ARB))
    if index < max_index and index >= 0 and length > 0:
        name = ctypes.create_string_buffer(length)
        size = arrays.GLintArray.zeros( (1,))
        gl_type = arrays.GLuintArray.zeros( (1,))
        base_glGetActiveAttribARB(program, index, length, None, size, gl_type, name)
        return name.value, size[0], gl_type[0]
    raise IndexError, 'index out of range from zero to %i' % (max_index - 1, )
glGetActiveAttribARB.wrappedOperation = base_glGetActiveAttribARB
