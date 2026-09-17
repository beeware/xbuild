from setuptools import Extension, setup

setup(
    ext_modules=[Extension("test1._native", sources=["src/test1/_native.c"])],
)
