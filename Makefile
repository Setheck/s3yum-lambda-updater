
# build zip archive for lambda upload (python2.7)
lambda:
	mkdir archive
	cp lambda_s3updater.py archive/
	cp -r vendor/* archive/
	zip archive.zip archive/*

clean:
	rm -rf archive archive.zip
