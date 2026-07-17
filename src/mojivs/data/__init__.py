"""Packaged data files for mojivs (e.g. the Adobe-Japan1 IVD table).

This module exists so that ``mojivs.data`` is a regular package rather than a
namespace package. ``importlib.resources.files("mojivs.data")`` fails on
Python 3.9 for namespace packages because ``spec.origin`` is ``None``.
"""
