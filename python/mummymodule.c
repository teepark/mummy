#include "Python.h"
#include "datetime.h"
#include "mummypy.h"


/* import decimal and datetime at mummy import time */
PyObject *PyDecimalType;
PyDateTime_CAPI *PyDateTimeCAPI;


static PyMethodDef methods[] = {
    {"dumps", (PyCFunction)python_dumps, METH_VARARGS | METH_KEYWORDS,
        "serialize a native python object into an mummy string"},
    {"loads", (PyCFunction)python_loads, METH_O,
        "deserialize a mummy string to a python object"},
    {NULL, NULL, 0, NULL}
};

#if ISPY3
static struct PyModuleDef _mummymodule = {
    PyModuleDef_HEAD_INIT,
    "_mummy",
    "",
    -1,
    methods,
    NULL,
    NULL,
    NULL,
    NULL
};

PyMODINIT_FUNC
PyInit__mummy(void) {
    PyObject *mummy_module, *decimal_module;

    mummy_module = PyModule_Create(&_mummymodule);

    PyDateTime_IMPORT;
    PyDateTimeCAPI = PyDateTimeAPI;

    decimal_module = PyImport_ImportModule("decimal");
    PyDecimalType = PyObject_GetAttrString(decimal_module, "Decimal");
    Py_INCREF(PyDecimalType);

    return module;
}
#else
PyMODINIT_FUNC
init_mummy(void) {
    PyObject *decimal_module;

    Py_InitModule("_mummy", methods);

    PyDateTime_IMPORT;
    PyDateTimeCAPI = PyDateTimeAPI;

    decimal_module = PyImport_ImportModule("decimal");
    PyDecimalType = PyObject_GetAttrString(decimal_module, "Decimal");
    Py_INCREF(PyDecimalType);
    Py_DECREF(decimal_module);
}
#endif
