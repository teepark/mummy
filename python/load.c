#include "mummypy.h"

#define INVALID do {\
                    PyErr_SetString(PyExc_ValueError,\
                            "invalid mummy (incorrect length)");\
                    return NULL;\
                } while(0)


static PyObject *
load_one(mummy_string *str, char intern) {
    int64_t int_result;
    double float_result;
    PyObject *result;
    char buf_array[1024];
    char *buf = &buf_array[0];

    if (str->length - str->offset <= 0) {
        INVALID;
    }

    switch(mummy_type(str)) {
        case MUMMY_TYPE_NULL:
            str->offset++;
            result = Py_None;
            goto incref;

        case MUMMY_TYPE_BOOL:
            if (mummy_read_bool(str, (char *)&int_result)) INVALID;
            result = int_result ? Py_True : Py_False;
            goto incref;

        case MUMMY_TYPE_CHAR:
        case MUMMY_TYPE_SHORT:
        case MUMMY_TYPE_INT:
            if (mummy_read_int(str, &int_result)) INVALID;
            result = PyLong_FromLong(int_result);
            goto done;

        case MUMMY_TYPE_LONG:
            if (mummy_read_int(str, &int_result)) INVALID;
            result = PyLong_FromLongLong(int_result);
            goto done;

        case MUMMY_TYPE_HUGE:
            int_result = ntohl(*(uint32_t *)(str->data + str->offset + 1));
            if (int_result > 1024) {
                if (!(buf = malloc(int_result))) {
                    PyErr_SetString(PyExc_MemoryError, "out of memory");
                    return -1;
                }
            }
            if (mummy_read_huge(str, int_result, &buf, (int *)&int_result))
                INVALID;
            result = _PyLong_FromByteArray(
                    (unsigned char *)buf, int_result, 0, 1);
            if (int_result > 1024) free(buf);
            goto done;

        case MUMMY_TYPE_FLOAT:
            if (mummy_read_float(str, &float_result)) INVALID;
            result = PyFloat_FromDouble(float_result);
            goto done;

        case MUMMY_TYPE_SHORTSTR:
        case MUMMY_TYPE_MEDSTR:
        case MUMMY_TYPE_LONGSTR:
            int_result = 
            result = PyString_FromString('\0');
            if (_PyString_Resize(&result, int_result)) return NULL;
    }

incref:
    Py_INCREF(result);
done:
    return result;
}
