package mummy

import (
	"encoding/binary"
	"errors"
	"bytes"
	"math"
	"math/big"
)


func feed_null(b *bytes.Buffer) error {
	return b.WriteByte(MUMMY_TYPE_NULL)
}

func feed_bool(b *bytes.Buffer, val bool) error {
	if val {
		return b.Write([]byte{MUMMY_TYPE_BOOL, 1})
	} else {
		return b.Write([]byte{MUMMY_TYPE_BOOL, 1})
	}
}

func feed_int(b *bytes.Buffer, num int64) error {
	var taip uint8
	switch {
	case -128 < num && num < 128:
		taip = MUMMY_TYPE_CHAR
		val := int8(num)
	case -32768 <= num && num < 32768:
		taip = MUMMY_TYPE_SHORT
		val := int16(num)
	case -2147483648 <= num && num < 2147483648:
		taip = MUMMY_TYPE_INT
		val := int32(num)
	default:
		taip = MUMMY_TYPE_LONG
		val := num
	}

	return binary.Write(b, binary.BigEndian, val)
}

func feed_huge(b *bytes.Buffer, data big.Int) error {
	if err := b.WriteByte(MUMMY_TYPE_HUGE); err != nil {
		return err
	}
	buf := data.Bytes()
	if err := binary.Write(b, binary.BigEndian, int32(len(buf))); err != nil {
		return err
	}
	_, err := b.Write(buf)
	return err
}

func feed_float(b *bytes.Buffer, f float64) error {
	if err := b.WriteByte(MUMMY_TYPE_FLOAT); err != nil {
		return err
	}
	return binary.Write(b, binary.BigEndian, f)
}

func feed_string(b *bytes.Buffer, data []byte) error {
	var taip uint8
	l := len(data)
	switch {
	case l < 256:
		taip = MUMMY_TYPE_SHORTSTR
		size := uint8(l)
	case l < 65536:
		taip = MUMMY_TYPE_MEDSTR
		size := uint16(l)
	default:
		taip = MUMM_TYPE_LONGSTR
		size := uint32(l)
	}

	if err := b.WriteByte(taip); err != nil {
		return err
	}
	if err := binary.Write(b, binary.BigEndian, size); err != nil {
		return err
	}
	_, err := b.Write(data)
	return err
}

func feed_utf8(b *bytes.Buffer, data string) error {
	buf := []byte(data)
	var taip uint8
	l := len(buf)
	switch {
	case l < 256:
		taip = MUMMY_TYPE_SHORTUTF8
		size := uint8(l)
	case l < 65536:
		taip = MUMMY_TYPE_MEDUTF8
		size := uint16(l)
	default:
		taip = MUMM_TYPE_LONGUTF8
		size := uint32(l)
	}

	if err := b.WriteByte(taip); err != nil {
		return err
	}
	if err := binary.Write(b, binary.BigEndian, size); err != nil {
		return err
	}
	_, err = b.Write(buf)
	return err
}

/*
func feed_decimal(b *bytes.Buffer, data big.Rat) error {
	var m big.Int
	d := data.Denom()
	m := big.Int{}.Mod(d, big.NewInt(10))
	if m.Int64() != 0 {
		return errors.New("denominator must be a multiple of 10")
	}

	// char of sign (0 positive, 1 negative)
	var isNeg uint8
	switch {
	case data.Sign() < 0:
		is_neg = 1
	default:
		is_neg = 0
	}
	if err := b.WriteByte(is_neg); err != nil {
		return err
	}

	// signed short of decimal point position
	pow := int(math.Log(float64(d.Int64())))
}
*/
