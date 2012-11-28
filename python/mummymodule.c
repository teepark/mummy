#include "Python.h"
#include "datetime.h"
#include "mummypy.h"


/* import decimal and datetime at mummy import time */
PyObject *PyDecimalType;
PyDateTime_CAPI *PyDateTimeCAPI;


static PyMethodDef methods[] = {
    {"dumps", (PyCFunction)python_dumps, METH_VARARGS | METH_KEYWORDS,
        "serialize a native python object into an mummy string\n\
\n\
    :param object: the python object to serialize\n\
    :param function default:\n\
        If the 'object' parameter is not serializable and this parameter is\n\
        provided, this function will be used to generate a fallback value to\n\
        serialize. It should take one argument (the original object), and\n\
        return something serializable.\n\
    :param bool compress:\n\
        whether or not to attempt to compress the serialized data (default\n\
        True)\n\
\n\
    :returns: the bytestring of the serialized data\n\
"},
    {"loads", (PyCFunction)python_loads, METH_O,
        "deserialize a mummy string to a python object\n\
\n\
    :param bytestring serialized: the serialized string to load\n\
\n\
    :returns: the python data\n\
"},
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
