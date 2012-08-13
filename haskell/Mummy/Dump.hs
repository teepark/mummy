module Mummy.Dump2
( dumps
, dump
) where

import Control.Applicative ((<$>), (<*>))
import Control.Monad (mapM_)
import qualified Data.ByteString as BS
    (ByteString, concat, length, pack, singleton, unpack)
import qualified Data.ByteString.Lazy as LBS
    (empty, ByteString, fromChunks, length, toChunks, unpack)
import qualified Data.ByteString.UTF8 as UTF8 (fromString)
import Data.Binary.IEEE754 (putFloat64be)
import Data.Binary.Put (Put, runPut, putByteString, putWord8)
import Data.Bits ((.&.), (.|.), shiftR, shiftL)
import Data.Int (Int64)
import Data.Word (Word8, Word16, Word32)
import Data.Decimal (DecimalRaw, decimalMantissa, decimalPlaces)
import Data.Time.Calendar (Day, toGregorian)
import Data.Time.Clock
    (UTCTime, utctDay, utctDayTime, DiffTime, NominalDiffTime)
import qualified Data.Set as Set (Set, size, toList)
import qualified Data.Map as Map (Map, size, toList)


-- typeclass for serialization
--
class MummySerializable a where
    dumps :: a -> BS.ByteString
    dumps = BS.concat . toChunks . runPut . dump

    dump :: a -> Put
    dump = putByteString . dumps

    -- list dumping gets delegated to the contained type
    -- so that [Char] can behave differently
    dumpList :: [a] -> LBS.ByteString
    dumpList x = runPut $ putCollectionHeader x >> mapM_ dump x


-- with Maybe types ignore Just and encode Nothing as Null
--
instance MummySerializable a => MummySerializable (Maybe a) where
    dumps Nothing  = BS.singleton 0
    dumps (Just x) = dumps x


-- bools go in 2 bytes
--
instance MummySerializable Bool where
    dumps False = BS.pack [1, 0]
    dumps True  = BS.pack [1, 1]


-- big-endian bytes of a number
--
numToWords :: Integral a => a -> [Word8]
numToWords = reverse . rec . fromIntegral where
    rec :: Int -> [Word8]
    rec 0 = []
    rec x = fromIntegral (x .&. 0xFF) : (rec $ shiftR x 8)

-- ensure a minimum length
--
padTo :: Integral a => a -> b -> [b] -> [b]
padTo size pad lst = replicate times pad ++ lst
    where times = mod (- length lst) (fromIntegral size)

-- size an integer
--
sizeNum :: Integral a => a -> Word8
sizeNum i | i >= -128        && i < 256        = 1
          | i >= -32768      && i < 32768      = 2
          | i >= -2147483648 && i < 2147483648 = 4
          | otherwise                          = 8

-- serialize an integer
--
serNum :: Integral a => a -> [Word8]
serNum i = padTo (sizeNum i) 0 . numToWords $ i

-- write integers to 2- and 4-byte strings
--
enc16be :: Integral a => a -> [Word8]
enc16be i = map fromIntegral $ [high, low]
    where j = fromIntegral i :: Word16
          high = j `shiftR` 8
          low  = j .&. 0xFF

enc32be :: Integral a => a -> [Word8]
enc32be i = map fromIntegral $ [high, medhi, medlo, low]
    where j = fromIntegral i :: Word32
          high  =  j `shiftR` 24
          medhi = (j `shiftR` 16) .&. 0xFF
          medlo = (j `shiftR` 8)  .&. 0xFF
          low   =  j              .&. 0xFF

-- typecodes for various ints by size
--
intType :: Word8 -> Word8
intType 1 = 2
intType 2 = 3
intType 4 = 4
intType 8 = 5


-- Ints may take up 1, 2 or 4 bytes depending on their size
--
instance MummySerializable Int where
    dumps x = BS.pack $ intType (sizeNum x) : serNum x


-- Integers get a 4 byte length header
--
instance MummySerializable Integer where
    dumps x | sizeNum x < 8 = dumps (fromInteger x :: Int)
            | otherwise     = let p = numToWords x
                              in BS.pack $ 6 : enc32be (length p) ++ p

-- Doubles go straight in as their IEEE754 encoding
--
instance MummySerializable Double where
    -- implementing `dump` instead of `dumps` because
    -- the IEEE754 package provides Put-monad functions
    dump x = putWord8 7 >> putFloat64be x


-- ad-hoc interface for both ByteString types
--
class AnyByteString bs where
    bslen :: bs -> Int
    toChunks :: bs -> [BS.ByteString]

instance AnyByteString LBS.ByteString where
    bslen = fromIntegral . LBS.length
    toChunks = LBS.toChunks

instance AnyByteString BS.ByteString where
    bslen = BS.length
    toChunks x = [x]
    

-- typecodes for various strings by size. pass True for UTF8
--
strType :: AnyByteString a => Bool -> a -> Word8
strType False s | bslen s < 256   = 8
                | bslen s < 65536 = 24
                | otherwise       = 9
strType True s | bslen s < 256   = 10
               | bslen s < 65536 = 25
               | otherwise       = 11

-- encode the size header for string/utf8 types
--
strHeaderEnc :: Integral a => a -> [Word8]
strHeaderEnc len | len < 256   = [fromIntegral len]
                 | len < 65536 = enc16be len
                 | otherwise   = enc32be len


-- two ByteStrings, one stone
--
{-
instance (AnyByteString bs) => MummySerializable bs where
    dumps x = BS.concat $ typecode : len : toChunks x
        where typecode = BS.singleton . strType False $ x
              len      = BS.pack . strHeaderEnc . bslen $ x
-}
dumpByteString :: AnyByteString a => a -> BS.ByteString
dumpByteString x = BS.concat $ typecode : len : toChunks x
    where typecode = BS.singleton . strType False $ x
          len      = BS.pack . strHeaderEnc . bslen $ x

instance MummySerializable BS.ByteString where
    dumps = dumpByteString

instance MummySerializable LBS.ByteString where
    dumps = dumpByteString


-- String/[Char]s need UTF8-encoding
--
-- the tricky part is that [Char] needs a different implementation
-- from [anything-dumpable], so we'll attach the real implementation
-- to the contained types
--
instance MummySerializable Char where
    dump = dump . (:[])

    dumpList x = LBS.fromChunks $ typecode : len : toChunks bs
        where bs       = UTF8.fromString x
              typecode = BS.singleton . strType True $ bs
              len      = BS.pack . strHeaderEnc . bslen $ bs


-- list the base 10 digits in a number in big-endian-like order
--
digitizeMe :: Integral a => a -> [Int]
digitizeMe = reverse . rec . abs . fromIntegral
    where rec :: Integer -> [Int]
          rec 0 = []
          rec i = (fromIntegral i) `mod` 10 : rec (i `div` 10)

-- take ints that fit in 4 bits and pack them in bytes in (low, hi) pairs
--
doublePackBytes :: [Int] -> [Word8]
doublePackBytes = rec True 0
    where rec :: Bool -> Word8 -> [Int] -> [Word8]
          rec _     _ []     = []
          rec True  y (x:xs) = rec False (fromIntegral x) xs
          rec False y (x:xs) = (fromIntegral (x `shiftL` 4) .|. y) : rec True 0 xs

-- Decimals have a custom encoding:
-- * 1 byte sign (just 1 for negative, 0 for positive)
-- * signed 2-byte decimal point position (from the right)
-- * unsgined 2-byte number of digits
-- * digits (nums 0-9) paired up in bytes, low 4 then high 4
--
instance Integral i => MummySerializable (DecimalRaw i) where
    dumps x = BS.pack $ 30 : sign : enc16be posn ++ enc16be len ++ bytes
        where sign | decimalMantissa x < 0 = 1
                   | otherwise             = 0
              posn   = - (fromIntegral . decimalPlaces) x
              digits = digitizeMe . decimalMantissa $ x
              len    = length digits
              bytes  = doublePackBytes digits


-- type for [s]NaN and [-]Infinity, instance for Num
--
data SpecialNum = Infinity { isNeg :: Bool } | NaN | SNaN deriving (Show)

instance Num SpecialNum where
    SNaN             + _                = error "SNaN is not defined"
    NaN              + _                = NaN
    (Infinity True)  + (Infinity False) = NaN
    (Infinity False) + _                = Infinity False
    (Infinity True)  + _                = Infinity True

    SNaN             * _                = error "SNaN is not defined"
    NaN              * _                = NaN
    (Infinity False) * (Infinity False) = Infinity False
    (Infinity True)  * (Infinity True)  = Infinity False
    (Infinity True)  * (Infinity False) = Infinity True

    SNaN         - _            = error "SNaN is not defined"
    NaN          - _            = NaN
    a            - (Infinity x) = a + (Infinity (not x))
    (Infinity x) - a            = (Infinity x) + (- a)

    negate SNaN         = error "SNaN is not defined"
    negate NaN          = NaN
    negate (Infinity x) = Infinity (not x)

    abs SNaN         = error "SNaN is not defined"
    abs NaN          = NaN
    abs (Infinity _) = Infinity False

    signum SNaN             = error "SNaN is not defined"
    signum NaN              = 1
    signum (Infinity False) = 1
    signum (Infinity True)  = -1

    fromInteger x = error "SpecialNums cannot be created from Integers"

instance MummySerializable SpecialNum where
    dumps (Infinity False) = BS.pack [31, 0x10]
    dumps (Infinity True)  = BS.pack [31, 0x11]
    dumps NaN              = BS.pack [31, 0x20]
    dumps SNaN             = BS.pack [31, 0x21]


-- date dumping
--
dumpDate :: Day -> [Word8]
dumpDate date = enc16be year ++ map fromIntegral [month, day]
    where (year, month, day) = toGregorian date

instance MummySerializable Day where
    dumps = BS.pack . (26:) . dumpDate

-- time dumping
--
dumpTime :: DiffTime -> [Word8]
dumpTime time = map fromInteger [hour, min, sec] ++ enc32be micro
    where seconds = floor time
          hour    = seconds `div` 3600
          min     = (seconds `mod` 3600) `div` 60
          sec     = seconds `mod` 60
          micro   = floor (time * 1000000) `mod` 1000000

instance MummySerializable DiffTime where
    dumps = BS.pack . (27:) . dumpTime

-- datetime: just combine a date and time
--
instance MummySerializable UTCTime where
    dumps = BS.pack . (28:) . dumpdt
        where dumpdt = (++) <$> dumpDate . utctDay <*> dumpTime . utctDayTime

-- use NominalDiffTime as timedelta
--
instance MummySerializable NominalDiffTime where
    dumps x = BS.pack . (29:) $ foldr1 (++) (map enc32be [day, sec, micro])
        where fl    = floor x
              day   = fl `div` 86400
              sec   = fl `mod` 86400
              micro = floor (x * 1000000) `mod` 1000000


-- generalized length function for a DRY putCollectionHeader
--
class MummySerializable a => MummyCollection a where
    mclength :: a -> Int
    typecode :: a -> Word8

collectionHeader :: MummyCollection a => a -> [Word8]
collectionHeader lst
    | len < 256   = [tc, fromIntegral len]
    | len < 65536 = tc : enc16be len
    | otherwise   = tc : enc32be len
    where tc  = typecode lst
          len = mclength lst

putCollectionHeader :: MummyCollection a => a -> Put
putCollectionHeader = putByteString . BS.pack . collectionHeader


-- MummyCollection and MummySerializable instances for list
--
instance MummySerializable a => MummyCollection [a] where
    mclength = length
    typecode x | length x < 256   = 0x10
               | length x < 65536 = 0x14
               | otherwise       = 0x0C

instance MummySerializable a => MummySerializable [a] where
    dump = (mapM_ putByteString) . toChunks . dumpList


-- tuple types
--
instance ( MummySerializable a
         , MummySerializable b) => MummyCollection (a, b) where
    mclength _ = 2
    typecode _ = 0x11

instance ( MummySerializable a
         , MummySerializable b) => MummySerializable (a, b) where
    dump s@(x, y) = putCollectionHeader s >> dump x >> dump y

instance ( MummySerializable a
         , MummySerializable b
         , MummySerializable c ) => MummyCollection (a, b, c) where
    mclength _ = 3
    typecode _ = 0x11

instance ( MummySerializable a
         , MummySerializable b
         , MummySerializable c ) => MummySerializable (a, b, c) where
    dump s@(x, y, z) = putCollectionHeader s >> dump x >> dump y >> dump z

instance ( MummySerializable a
         , MummySerializable b
         , MummySerializable c
         , MummySerializable d ) => MummyCollection (a, b, c, d) where
    mclength _ = 4
    typecode _ = 0x11

instance ( MummySerializable a
         , MummySerializable b
         , MummySerializable c
         , MummySerializable d ) => MummySerializable (a, b, c, d) where
    dump s@(w, x, y, z) = putCollectionHeader s >> dump w >> dump x
                          >> dump y >> dump z

instance ( MummySerializable a
         , MummySerializable b
         , MummySerializable c
         , MummySerializable d
         , MummySerializable e ) => MummyCollection (a, b, c, d, e) where
    mclength _ = 5
    typecode _ = 0x11

instance ( MummySerializable a
         , MummySerializable b
         , MummySerializable c
         , MummySerializable d
         , MummySerializable e ) => MummySerializable (a, b, c, d, e) where
    dump s@(v, w, x, y, z) = putCollectionHeader s >> dump v >> dump w
                             >> dump x >> dump y >> dump z

instance ( MummySerializable a
         , MummySerializable b
         , MummySerializable c
         , MummySerializable d
         , MummySerializable e
         , MummySerializable f ) => MummyCollection (a, b, c, d, e, f) where
    mclength _ = 6
    typecode _ = 0x11

instance ( MummySerializable a
         , MummySerializable b
         , MummySerializable c
         , MummySerializable d
         , MummySerializable e
         , MummySerializable f ) => MummySerializable (a, b, c, d, e, f) where
    dump s@(u, v, w, x, y, z) = putCollectionHeader s >> dump u >> dump v
                                >> dump w >> dump x >> dump y >> dump z


-- Data.Set.Sets as mummy sets
--
instance MummySerializable a => MummyCollection (Set.Set a) where
    mclength = Set.size
    typecode s | mclength s < 256   = 0x12
               | mclength s < 65536 = 0x16
               | otherwise          = 0x0E

instance MummySerializable a => MummySerializable (Set.Set a) where
    dump s = putCollectionHeader s >> mapM_ dump (Set.toList s)

-- Data.Map.Maps as mummy hashes
--
instance (MummySerializable k,
          MummySerializable a) => MummyCollection (Map.Map k a) where
    mclength = Map.size
    typecode m | mclength m < 256   = 0x13
               | mclength m < 65536 = 0x17
               | otherwise          = 0x0F

instance (MummySerializable k,
          MummySerializable a) => MummySerializable (Map.Map k a) where
    dump m = putCollectionHeader m >> mapM_ dumpPair (Map.toList m)
        where dumpPair = \(k, v) -> dump k >> dump v
