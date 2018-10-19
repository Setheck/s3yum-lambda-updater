
# build zip archive for lambda upload (python2.7)
lambda:
	mkdir archive
	cp lambda_s3updater.py archive/
	cp -r vendor/* archive/
	cd archive && zip -r ../archive.zip *

clean:
	rm -rf archive archive.zip
