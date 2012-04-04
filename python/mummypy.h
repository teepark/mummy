#include "Python.h"
#include "datetime.h"
#include "mummy.h"


#define ISPY3 (PY_MAJOR_VERSION == 3)

#if !ISPY3
    #define PyBytes_CheckExact PyString_CheckExact
    #define PyBytes_AS_STRING PyString_AS_STRING
    #define PyBytes_GET_SIZE PyString_GET_SIZE
    #define PyBytes_FromStringAndSize PyString_FromStringAndSize
    #define PyInt_AsLongLong PyLong_AsLongLong
#endif

#define MUMMYPY_MAX_DEPTH 256
#define MUMMYPY_STARTING_BUFFER 0x1000

PyObject *python_dumps(PyObject *, PyObject *, PyObject *);
PyObject *python_loads(PyObject *, PyObject *);
