import zlib
import sys
import binascii


f_name = sys.argv[1]

f = open(f_name, 'rb')
deco_dat = zlib.decompress(f.read())

wf = open(f_name+'.deco', 'wb')
wf.write(deco_dat)
df = open(f_name+'.dmp', 'wb')
df.write(binascii.b2a_hex(deco_dat))

# idx = 0
# lno = 0

# line_chr_no = 4

# while True:
#     line = deco_dat[idx:idx+line_chr_no] if len(deco_dat) < idx +line_chr_no else deco_dat[idx:]
#     lno += 1
#     print len(line)

# #    print '%5d |%s|%s' % (lno, binascii.b2a_hex(line), line)

#     idx +=line_chr_no
#     if len(deco_dat) < idx:
#         break


