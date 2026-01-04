# setup.py - 编译 Cython 模块
from setuptools import setup
from Cython.Build import cythonize

setup(
    ext_modules=cythonize("core/fast_scan.pyx", language_level=3)
)
