from PySide2 import QtCore, QtGui, QtWidgets
from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import QObject, QPoint, QPointF, QFile, QSize, QSizeF, QRect, QRectF, QMimeData, Signal, Slot
from PIL import Image
import qdarkstyle
import numpy as np
from pathlib import Path
import ctypes
import time
import colorsys
import os

USE_DARK_THEME = True

if USE_DARK_THEME:
	os.environ['QT_API'] = 'pyqt'
	iconFolder = 'icons/dark'
	styleColor = (20, 140, 210) #'148cd2' #turquoise
else:
	iconFolder = 'icons/light'
	styleColor = (138, 198, 64) #'8ac546' #green

#this is necessary in order to display the correct taskbar icon
myappid = 'application.myQtApp' # arbitrary string
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

'''
 dialog box that requests a height and width (optional: constrain aspect ratio)
 usage: h, w, ok = GetDimensionsDialog.getValues(h=height, w=width, max=10000, constrain=True)
'''
class GetDimensionsDialog(QDialog):
	def __init__(self, h, w, min=1, max=100, constrain=False, parent=None):
		super(GetDimensionsDialog, self).__init__(parent)
		self.setWindowFlags(QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint)
		## Default values
		self.h = h
		self.w = w

		self.hL = QLabel("height:")
		self.hInput = QSpinBox(self)
		self.hInput.setMinimum(min)
		self.hInput.setMaximum(max)
		self.hInput.setValue(self.h)

		self.wL = QLabel("width:")
		self.wInput = QSpinBox(self)
		self.wInput.setMinimum(min)
		self.wInput.setMaximum(max)
		self.wInput.setValue(self.w)

		if constrain:
			self.aspectRatio = h/w
			self.hInput.valueChanged.connect(self.constrainW)
			self.wInput.valueChanged.connect(self.constrainH)

		self.OKBtn = QPushButton("OK")
		self.OKBtn.clicked.connect(self.accept)

		## Set layout, add buttons
		layout = QGridLayout()
		layout.setColumnStretch(1, 1)
		layout.setColumnMinimumWidth(1, 250)

		layout.addWidget(self.hL, 0, 0)
		layout.addWidget(self.hInput, 0, 1)
		layout.addWidget(self.wL, 1, 0)
		layout.addWidget(self.wInput, 1, 1)
		layout.addWidget(self.OKBtn, 2, 1)

		self.setLayout(layout)
		self.setWindowTitle("Select grid dimensions")

	def values(self):
		return self.hInput.value(), self.wInput.value()

	def constrainW(self):
		self.wInput.blockSignals(True)
		self.wInput.setValue(self.hInput.value() / self.aspectRatio )
		self.wInput.blockSignals(False)

	def constrainH(self):
		self.hInput.blockSignals(True)
		self.hInput.setValue(self.wInput.value() * self.aspectRatio )
		self.hInput.blockSignals(False)

	@staticmethod
	def getValues(h=1, w=1, min=1, max=100, constrain=False, parent=None):
		dialog = GetDimensionsDialog(h, w, min, max, constrain, parent)
		result = dialog.exec_()
		h, w = dialog.values()
		return h, w, result == QDialog.Accepted

'''
 dialog box that requests a selection from a dropdown box of strings
 usage: dataset, ok = GetDatasetDialog.getValue(datasets, currentDataset)
'''
class GetDatasetDialog(QDialog):
	def __init__(self, datasets, dataset, parent=None):
		super(GetDatasetDialog, self).__init__(parent)
		self.setWindowFlags(QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint)
		## Default values
		self.dL = QLabel("Choose dataset:")
		self.dInput = QComboBox(self)
		for d in datasets:
			self.dInput.addItem(d)

		self.dInput.setCurrentIndex(self.dInput.findText(dataset))
		self.OKBtn = QPushButton("OK")
		self.OKBtn.clicked.connect(self.accept)

		## Set layout, add buttons
		layout = QGridLayout()
		layout.setColumnStretch(1, 1)
		layout.setColumnMinimumWidth(1, 250)

		layout.addWidget(self.dL, 0, 0)
		layout.addWidget(self.dInput, 0, 1)
		layout.addWidget(self.OKBtn, 1, 1)

		self.setLayout(layout)
		self.setWindowTitle("Select dataset")

	def value(self):
		return self.dInput.currentText()

	@staticmethod
	def getValue(ds=None, d='', parent=None):
		dialog = GetDatasetDialog(ds, d, parent)
		result = dialog.exec_()
		return dialog.value(), result == QDialog.Accepted

class ImageViewer(QtWidgets.QGraphicsView):
	updateInfo = Signal(str)

	def __init__(self, parent):
		super(ImageViewer, self).__init__(parent)
		self._zoom = 0
		self._showGrid = False
		self._empty = True
		self.imageShape = QSize(0, 0)
		self._scene = QGraphicsScene(self)
		self._image = QGraphicsPixmapItem()
		self._scene.addItem(self._image)
		self.setScene(self._scene)
		self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
		self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
		self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
		self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
		self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(30, 30, 30))) #define dark gray background color
		self.setFrameShape(QtWidgets.QFrame.NoFrame)

		self.wheelSelection = 0
		self.mouseClickPosition = None
		self.leftMouseButtonDown = False
		self.middleMouseButtonDown = False
		self._panStart = QPoint(0, 0)

#-----------------------------------------------------------------------------------------------------------------------------------------
# HANDLING OF INHERITED EVENTS
#-----------------------------------------------------------------------------------------------------------------------------------------

	def enterEvent(self, event):
		pass

	def leaveEvent(self, event):
		pass

	def mouseMoveEvent(self, event):
		if self.middleMouseButtonDown:
			# panning behaviour
			delta = self._panStart - event.pos()

			self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + delta.x())
			self.verticalScrollBar().setValue(self.verticalScrollBar().value() + delta.y())
			self._panStart = event.pos()
			event.accept()
			return

		if self.hasImage():
			event.accept()

		super(ImageViewer, self).mouseMoveEvent(event)

	def mouseReleaseEvent(self, event):
		print('[viewer] mouseRelease')
		self.middleMouseButtonDown = False

		if self._image.isUnderMouse():
			#processing dragging
			if self.mouseClickPosition is not None and (event.pos() - self.mouseClickPosition).manhattanLength() > QApplication.startDragDistance():
				#handle dragging behaviour
				pass

		self.leftMouseButtonDown = False
		super(ImageViewer, self).mousePressEvent(event)

	def mousePressEvent(self, event):
		if self._image.isUnderMouse():
			if event.button() & QtCore.Qt.RightButton:
				print('right mouse button clicked!')
				pass

			elif event.button() & QtCore.Qt.MiddleButton:

				print('middle mouse button clicked! > panning')
				self.middleMouseButtonDown = True
				self._panStart = event.pos()

			elif event.button() & QtCore.Qt.LeftButton:
				print('left mouse button clicked at {}!'.format(self.mouseClickPosition))
				self.leftMouseButtonDown = True
				self.mouseClickPosition = event.pos()

	def wheelEvent(self, event):
		self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
		if self.hasImage():
			if event.angleDelta().y() > 0:
				factor = 1.25
				self._zoom += 1
			else:
				factor = 0.8
				self._zoom -= 1
			if self._zoom > 0:
				self.scale(factor, factor)
			elif self._zoom == 0:
				self.fitInView()
			else:
				self._zoom = 0

	def resizeEvent(self, event):
		self.fitInView()

# -----------------------------------------------------------------------------------------------------------------------------------------

	def hasImage(self):
		return not self._empty

	def getImageDims(self):
		return QRectF(self._image.pixmap().rect())

	def fitInView(self):
		rect = self.getImageDims()
		if not rect.isNull():
			self.setSceneRect(rect)
			if self.hasImage():
				unity = self.transform().mapRect(QRectF(0, 0, 1, 1))
				self.scale(1 / unity.width(), 1 / unity.height())
				viewrect = self.viewport().rect()
				scenerect = self.transform().mapRect(rect)
				factor = min(viewrect.width() / scenerect.width(),
							 viewrect.height() / scenerect.height())
				self.scale(factor, factor)
			self._zoom = 0

	def toggleGrid(self):
		if not self.hasImage():
			return
		self._showGrid = not self._showGrid
		self._scene.update()

	def loadImage(self, fname):
		pilImg = Image.open(fname)
		image = np.array(pilImg)
		if type(image) is np.ndarray: #if input type is numpy array, convert to pixmap
			image = self.pixmapFromArray(image)

		self._empty = False
		self._image.setPixmap(image)
		self.fitInView()

		self.updateInfo.emit('Image size: {}x{}'.format(image.width(), image.height()))

	'''
	override drawForeground method to paint grid cells
	'''
	def drawForeground(self, painter, rect):
		gridSize = QSize(10, 10)
		if self._showGrid:
			rect = self.getImageDims()

			pen = QPen(QColor(styleColor[0], styleColor[1], styleColor[2], 150), 3)
			pen.setStyle(QtCore.Qt.CustomDashLine)
			pen.setDashPattern([1, 2])

			painter.setPen(pen)

			d = rect.width() / gridSize.width()
			for y in range(1, gridSize.height()):
				painter.drawLine(QPoint(0, int(y * d)), QPoint(int(rect.width()), int(y * d)))

			for x in range(1, gridSize.width()):
				painter.drawLine(QPoint(int(x * d), 0), QPoint(int(x * d), int(rect.height())))

	'''
	convert numpy array to QPixmap
	'''
	def pixmapFromArray(self, array):
		self.imageShape = QSize(array.shape[1], array.shape[0])
		print('image shape: {}x{}'.format(array.shape[1], array.shape[0]))
		cp = array.copy()
		image = QImage(cp, array.shape[1], array.shape[0], QImage.Format_RGB888) #FIX this doesn't work for all images
		return QPixmap(image)

	def saveImage(self):
		filename = QFileDialog.getSaveFileName(self, 'Save image as...', str(Path.home())+'\Desktop')

		if filename is None or filename == "":
			return

		print(filename)
		self._image.pixmap().save(filename[0], "JPG")

class MainWidget(QtWidgets.QWidget):
	def __init__(self):
		super(MainWidget, self).__init__()
		self.viewer = ImageViewer(self)

		self.viewer.updateInfo.connect(self.setInformation)

		# 'Load image' button
		self.btnLoad = QToolButton(self)
		self.btnLoad.setIcon(QtGui.QIcon(iconFolder + '/icon_upload.png'))
		self.btnLoad.setToolTip('Open Image')
		self.btnLoad.setIconSize(QSize(32, 32))
		self.btnLoad.clicked.connect(self.loadImageDialog)

		# 'Save' button
		self.btnSave = QToolButton(self)
		icon = QIcon()
		icon.addPixmap(QPixmap(iconFolder + '/icon_download.png'), QIcon.Normal)
		icon.addPixmap(QPixmap(iconFolder + '/icon_download_disabled.png'), QIcon.Disabled)
		self.btnSave.setIcon(icon)
		self.btnSave.setToolTip('Save Image')
		self.btnSave.setEnabled(True)
		self.btnSave.setIconSize(QSize(32, 32))
		self.btnSave.clicked.connect(self.viewer.saveImage)

		# info box
		self.infoTextBox = QLineEdit(self)
		self.infoTextBox.setReadOnly(True)

		# 'toggle grid' button
		self.btnGrid = QToolButton(self)
		self.btnGrid.setCheckable(True)
		icon = QIcon()
		icon.addPixmap(QPixmap(iconFolder + '/icon_grid_disabled.png'), QIcon.Disabled)
		icon.addPixmap(QPixmap(iconFolder + '/icon_grid_off.png'), QIcon.Normal, QIcon.Off)
		icon.addPixmap(QPixmap(iconFolder + '/icon_grid.png'), QIcon.Normal, QIcon.On)
		self.btnGrid.setIcon(icon)
		self.btnGrid.setIconSize(QSize(32, 32))
		self.btnGrid.setToolTip('Show grid')
		self.btnGrid.setChecked(False)
		self.btnGrid.setEnabled(True)
		self.btnGrid.toggled.connect(self.viewer.toggleGrid)

		# Arrange layout
		VBlayout = QVBoxLayout(self)

		VBlayout.addWidget(self.viewer)

		HBlayout = QHBoxLayout()
		HBlayout.setAlignment(QtCore.Qt.AlignLeft)
		HBlayout.addWidget(self.btnLoad)
		HBlayout.addWidget(self.btnSave)
		HBlayout.addWidget(self.infoTextBox)
		HBlayout.addWidget(self.btnGrid)

		VBlayout.addLayout(HBlayout)
		self.viewer.fitInView()

	'''
	Dialog window to load file
	'''
	def loadImageDialog(self):
		#Get the file locationR
		filename, _ = QFileDialog.getOpenFileName(self, 'Open file', str(Path.home())+'\Desktop')

		if filename is None or filename == "":
			return

		self.fname = filename
		# Load the image from the location
		self.viewer.loadImage(self.fname)

	def setInformation(self, str):
		self.infoTextBox.setText(str)

class MainWindow(QMainWindow):
	def __init__(self, widget):
		QMainWindow.__init__(self)

		self.setWindowTitle("PyQt Image Viewer")
		app_icon = QtGui.QIcon()
		#set icon of window
		app_icon.addFile(iconFolder + '/icon_default.png')
		self.setWindowIcon(app_icon)

		## Exit Action
		exit_action = QAction("Exit", self)
		exit_action.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
		exit_action.triggered.connect(self.exit_app)

		# Window dimensions
		self.setCentralWidget(widget)

		geometry = app.desktop().availableGeometry(self)
		self.resize(int(geometry.height() * 0.85), int(geometry.height() * 0.6))

	@Slot()
	def exit_app(self, checked):
		sys.exit()

if __name__ == '__main__':
	import argparse
	import sys

	app = QtWidgets.QApplication(sys.argv)

	if USE_DARK_THEME:
		app.setStyleSheet(qdarkstyle.load_stylesheet())

	widget = MainWidget()

	# QMainWindow using QWidget as central widget
	window = MainWindow(widget)
	window.show()
	sys.exit(app.exec_())