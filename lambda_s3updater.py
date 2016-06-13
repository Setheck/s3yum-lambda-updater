
import urlparse
import logging
import sys
import tempfile
import createrepo
import yum
import boto
import os
import shutil
from rpmUtils.miscutils import splitFilename

# Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Hack for creating s3 urls
urlparse.uses_relative.append('s3')
urlparse.uses_netloc.append('s3')

sh = logging.StreamHandler(sys.stdout)
logger.addHandler(sh)

class LoggerCallback(object):
    def errorlog(self, message):
        logging.error(message)

    def log(self, message):
        message = message.strip()
        if message:
            logging.info(message)

class S3Grabber(object):
    def __init__(self, baseurl):
        base = urlparse.urlsplit(baseurl)
        self.baseurl = baseurl
        self.basepath = base.path.lstrip('/')
        self.bucket = boto.connect_s3().get_bucket(base.netloc)

    def _getkey(self, url):
        if url.startswith(self.baseurl):
            url = url[len(self.baseurl):].lstrip('/')
        key = self.bucket.get_key(os.path.join(self.basepath, url))
        if not key:
            raise createrepo.grabber.URLGrabError(14, '%s not found' % url)
        return key

    def urlgrab(self, url, filename, **kwargs):
        key = self._getkey(url)
        logging.debug('downloading: %s', key.name)
        key.get_contents_to_filename(filename)
        return filename

    def urldelete(self, url):
        key = self._getkey(url)
        logging.debug('removing: %s', key.name)
        key.delete()

    def syncdir(self, dir, url):
        """Copy all files in dir to url, removing any existing keys."""
        base = os.path.join(self.basepath, url)
        existing_keys = list(self.bucket.list(base))
        new_keys = []
        for filename in sorted(os.listdir(dir)):
            key = self.bucket.new_key(os.path.join(base, filename))
            key.set_contents_from_filename(os.path.join(dir, filename))
            new_keys.append(key.name)
            logging.debug('uploading: %s', key.name)
        for key in existing_keys:
            if key.name not in new_keys:
                logging.debug('removing: %s', key.name)
                key.delete()


def update_repodata(bucketName, key, operation):
    if key.rFind("/") > -1:
      fileName = key[key.rfind("/")+1:]
      repoPath = key[:key.rfind("/")]
    else:
      fileName = key
      repoPath = ""

    (name, version, release, epoch, arch) = splitFilename(fileName)

    logger.debug("fileName={0}".format(fileName))
    logger.debug("repoPath={0}".format(repoPath))

    tmpdir = tempfile.mkdtemp()

    s3base = urlparse.urlunsplit(("s3", bucketName, repoPath, "", ""))
    s3grabber = S3Grabber(s3base)

    # Set up temporary repo that will fetch repodata from s3
    yumbase = yum.YumBase()
    yumbase.preconf.disabled_plugins = '*'
    yumbase.conf.cachedir = os.path.join(tmpdir, 'cache')
    yumbase.repos.disableRepo('*')
    repo = yumbase.add_enable_repo('s3')
    repo._grab = s3grabber
    repo._urls = [os.path.join(s3base, '')]
    # Ensure that missing base path doesn't cause trouble
    repo._sack = yum.sqlitesack.YumSqlitePackageSack(
        createrepo.readMetadata.CreaterepoPkgOld)

    # Create metadata generator
    mdconf = createrepo.MetaDataConfig()
    mdconf.directory = tmpdir
    mdconf.pkglist = yum.packageSack.MetaSack()
    mdgen = createrepo.MetaDataGenerator(mdconf, LoggerCallback())
    mdgen.tempdir = tmpdir
    mdgen._grabber = s3grabber

    new_packages = yum.packageSack.PackageSack()
    if operation == "add":
        # Combine existing package sack with new rpm file list
        newpkg = mdgen.read_in_package(os.path.join(s3base, fileName))
        newpkg._baseurl = ''   # don't leave s3 base urls in primary metadata
        new_packages.addPackage(newpkg)
    else:
        # Remove deleted package
        logger.debug("Delete package {0}".format(key))
        older_pkgs = yumbase.pkgSack.searchNevra(name=name)
        for i, older in enumerate(older_pkgs, 1):
            if older.version == version and older.release == release:
                yumbase.pkgSack.delPackage(older)

    mdconf.pkglist.addSack('existing', yumbase.pkgSack)
    mdconf.pkglist.addSack('new', new_packages)

    # Write out new metadata to tmpdir
    mdgen.doPkgMetadata()
    mdgen.doRepoMetadata()
    mdgen.doFinalMove()

    # Replace metadata on s3
    s3grabber.syncdir(os.path.join(tmpdir, 'repodata'), 'repodata')

    shutil.rmtree(tmpdir)


def handle(event, context):
    record = event['Records'][0]
    eventType = record['eventName']
    s3Elem = record['s3']
    bucketName = s3Elem['bucket']['name']
    key = s3Elem['object']['key']

    logger.debug("Got Event {0}:{1}/{2}".format(eventType, bucketName, key))

    if "Created" in eventType:
        update_repodata(bucketName, key, "add")
    elif "Removed" in eventType and "Marker" not in eventType:
        update_repodata(bucketName, key, "remove")
    else:
        logger.error("Ignoring EventType {0}".format(eventType))
