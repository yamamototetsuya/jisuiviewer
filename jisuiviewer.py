# coding: utf8

# 自炊データビューア

import zlib
import zipfile
import glob
from StringIO import StringIO
from PIL import Image, ImageOps, ImageEnhance

import pygame

#
# read lines from file. handle both CR and LF
#
def linesgen_crlf(f):
  while 1:
    l = f.readline()
    if not l:
      yield None
      return
    i = 0
    while 1:
      p = l.find("\r", i)
      if p == -1:
        yield l[i:]
        break
      else:
        yield l[i:p+1]
        i = p+1

#
# get image list from pdf data and
# generate position list (in that file)
# dirty PDF parsing!
#
def get_imagelist_from_pdf(f):
  fg = linesgen_crlf(f)
  icnt = 1
  images = []
  while 1:
    #l = f.readline()
    l = fg.next()
    if not l: break
    c = l.rstrip()
    if c.endswith("obj"):
      # detect obj
      b = []
      strpos, strlen = 0, 0
      while 1:
        #ll = f.readline()
        ll = fg.next()
        cc = ll.rstrip()
        if cc == 'endobj':
          break
        b.append(cc)

        if cc.endswith('stream'):
          # detect stream
          strpos = f.tell()
          while 1:
            #lll = f.readline()
            lll = fg.next()
            ccc = lll.rstrip()
            if ccc == 'endstream':
              break
            strlen += len(lll)

      objstr = " ".join(b)

      if "/Image" in objstr and "/ImageI" not in objstr:
        if "/FlateDecode" in objstr:
          # bitmap image(assumimg 1bit bitmap... dirty)
          oo = objstr.replace("/", " /").replace(">>", " >>").split(" ")
          w, h = -1, -1
          for i in range(len(oo)-1):
            if oo[i] == '/Width':
              w = int(oo[i+1])
            elif oo[i] == '/Height':
              h = int(oo[i+1])
          images.append(("%05d.bmp" % icnt, "bitmap", w, h, strpos, strlen))
          icnt += 1
        elif "/DCTDecode" in objstr:
          # jpeg image
          images.append(("%05d.jpg" % icnt, "jpeg", 0, 0, strpos, strlen))
          icnt += 1
  return images


# adjust contrast of given image
def adjust_image(img):
  ih = ImageEnhance.Contrast(img)
  return ih.enhance(1.5)


#
# image list holder (pdf)
#
class PDFImageList(object):

  def __init__(self, pdffile):
    self.f = open(pdffile, 'rb')
    self.images = get_imagelist_from_pdf(self.f)
    self.imagenum = len(self.images)

  def image(self, pos):
    im = self.images[pos]
    self.f.seek(im[4])
    streamstr = self.f.read(im[5])
    if im[1] == 'jpeg':
      i1 = Image.open(StringIO(streamstr))
      i1 = i1.convert("RGB")
      return adjust_image(i1)
    elif im[1] == 'bitmap':
      streamstr = zlib.decompress(streamstr)
      i1 = Image.frombuffer("1", (im[2], im[3]), streamstr, "raw", "1", 0, 1)
      i1 = ImageOps.invert(i1.convert("RGB"))
      return i1


#
# image list holder (image directory)
#
class DirImageList(object):

  def __init__(self, imagedir):
    self.images = glob.glob(imagedir + '/*.jpg') + glob.glob(imagedir + '/*.jpeg') + glob.glob(imagedir + '/*.png')
    self.imagenum = len(self.images)

  def image(self, pos):
    im = self.images[pos]
    i1 = Image.open(im).convert("RGB")
    return adjust_image(i1)


# image list holder (image zipfile)
class ZipImageList(object):

  def __init__(self, zipfilename):

    self.z = zipfile.ZipFile(zipfilename, 'r')
    self.images = [i for i in self.z.namelist() if i.endswith('.jpg') or i.endswith('.jpeg') or i.endswith('.png')]
    self.imagenum = len(self.images)

  def image(self, pos):
    o = self.z.read(self.images[pos])
    sio = StringIO(o)
    i1 = Image.open(sio).convert("RGB")
    return adjust_image(i1)

#
# imprements page moving feature
#
class ImageBook(object):

  def __init__(self, imagelist):
    self.imagelist = imagelist
    self.bookpages = imagelist.imagenum

    self.pos = 0
    self.page1 = self.prepare_image1()
    self.page2 = self.prepare_image2()

  def prepare_image1(self):
    i = self.pos % self.bookpages
    return self.imagelist.image(i)

  def prepare_image2(self):
    i = (self.pos+1) % self.bookpages
    return self.imagelist.image(i)

  def proceed(self):
    self.pos += 2
    self.page1 = self.prepare_image1()
    self.page2 = self.prepare_image2()

  def proceed_one(self):
    self.pos += 1
    self.page1 = self.page2
    self.page2 = self.prepare_image2()

  def back(self):
    self.pos -= 2
    self.page1 = self.prepare_image1()
    self.page2 = self.prepare_image2()

  def back_one(self):
    self.pos -= 1
    self.page2 = self.page1
    self.page1 = self.prepare_image1()


#
# imprements user interaction
#
class ImageBookViewer(object):
  def __init__(self, book, surface):
    self.swidth = surface.get_width() / 2
    self.sheight = surface.get_height()
    self.book = book
    self.surface = surface
    self.direction = 'l'
    self.quickrender = False

  def show_pages(self):
    if self.quickrender:
      resizeop = Image.NEAREST
    else:
      resizeop = Image.ANTIALIAS
      #resizeop = Image.BICUBIC

    if self.direction=='r':
      i = self.book.page1.resize((self.swidth, self.sheight), resizeop)
      s1 = pygame.image.fromstring(i.tostring(), i.size, i.mode).convert()
      self.surface.blit(s1, (0, 0))

      i = self.book.page2.resize((self.swidth, self.sheight), resizeop)
      s2 = pygame.image.fromstring(i.tostring(), i.size, i.mode).convert()
      self.surface.blit(s2, (self.swidth, 0))

    else:
      i = self.book.page1.resize((self.swidth, self.sheight), resizeop)
      s1 = pygame.image.fromstring(i.tostring(), i.size, i.mode).convert()
      self.surface.blit(s1, (self.swidth, 0))

      i = self.book.page2.resize((self.swidth, self.sheight), resizeop)
      s2 = pygame.image.fromstring(i.tostring(), i.size, i.mode).convert()
      self.surface.blit(s2, (0, 0))
    pygame.display.update()

  def handle_leftkey(self):
    if self.direction=='r':
      self.book.back_one()
    else:
      self.book.proceed_one()
    self.show_pages()

  def handle_rightkey(self):
    if self.direction=='r':
      self.book.proceed_one()
    else:
      self.book.back_one()
    self.show_pages()

  def handle_upkey(self):
    self.book.back()
    self.show_pages()

  def handle_downkey(self):
    self.book.proceed()
    self.show_pages()

  def view(self):
      self.show_pages()
      pygame.display.update()

      while 1:
        e = pygame.event.wait()
        if e.type == pygame.QUIT:
          return
        elif e.type == pygame.KEYDOWN:
          if e.key == 27:
            return
          #print e.key, e.unicode
          if e.key == 274:
            self.handle_downkey()
          elif e.key == 273:
            self.handle_upkey()
          elif e.key == 275:
            self.handle_rightkey()
          elif e.key == 276:
            self.handle_leftkey()
          elif e.unicode == u'f':
            if self.direction == 'r':
              self.direction = 'l'
            else:
              self.direction = 'r'
            self.show_pages()
          elif e.unicode == u'q':
            self.quickrender = not self.quickrender
            self.show_pages()

#
# see pathname and select suitable ImageList object
#
def GenImageBook(pathname):
  if pathname.endswith('.pdf'):
    p = PDFImageList(pathname)
  elif pathname.endswith('.zip') or pathname.endswith('.cbz'):
    p = ZipImageList(pathname)
  else:
    p = DirImageList(pathname)
  m = ImageBook(p)
  return m



def main():
  
  m = GenImageBook(bookname)
  pygame.init()
  s = pygame.display.set_mode((640,480))
  #s = pygame.display.set_mode((0,0), pygame.FULLSCREEN)
  mv = ImageBookViewer(m, s)
  mv.view()
  pygame.quit()


bookname = u'c:\\some\\path\\to\\imagedir'
#bookname = u'c:\\some\\path\\to\\zip.zip'
#bookname = u'c:\\some\\path\\to\\pdf.pdf'
main()


"""
#
# **OMAKE** (export all images from pdf)
#
pdffile = r'c:\some\path\to\pdf.pdf'
p = PDFImageList(pdffile)
n = 1
for im in p.images:
  p.f.seek(im[4])
  content = p.f.read(im[5])
  if im[1] == 'jpeg':
     open("%05d.jpg" % n, "wb").write(content)
  elif im[1] == 'bitmap':
     imgdata = zlib.decompress(content)
     img = Image.frombuffer("1", (im[2], im[3]), imgdata, "raw", "1", 0, 1)
     img = ImageOps.invert(img.convert("RGB"))
     img.save("%05d.png" % n)
  n += 1
"""
