#define PY_SSIZE_T_CLEAN
#include <Python.h>

static PyObject *
answer(PyObject *self, PyObject *args)
{
    return PyLong_FromLong(42);
}

static PyMethodDef methods[] = {
    {"answer", answer, METH_NOARGS, "Return the answer to everything."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "_native",
    NULL,
    -1,
    methods,
};

PyMODINIT_FUNC
PyInit__native(void)
{
    return PyModule_Create(&moduledef);
}
