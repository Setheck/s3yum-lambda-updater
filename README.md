This AWS lambda function can be used to keep an s3-hosted yum repository
updated when rpm packages are uploaded / deleted. It is equivalent to using
`createrepo` and an `s3cmd sync`. Only a temporary copy of the repo metadata
is needed locally, so there's no need to keep a full close of the repository
and all it's packages. This data is also very useful if packages are
uploaded by many users or systems. Having a single lambda function will
ensure all new packages are added to the repository metadata, avoiding
issues with concurrent updates.

The upload of a new package to s3 should be handled by whatever client is
used to build the rpm, e.g. a CI system like Jenkins. The S3 bucket should
be configured to send events to the lambda function when a file is uploaded
or deleted. The function then downloads the repodata, the new rpm (if added), 
updates and uploads back to the S3 bucket.

---

For full step-by-step installation instructions see [docs/install.md](docs/install.md).

Install
-------

See the releases section of the repo for pre-built zip files containing required
dependencies.

Configure
---------

Create an S3 bucket to host the yum repository. Create a lambda function, with 
appropriate access to the bucket. Add the S3 event to the bucket and point at the 
lambda function.

Related Tools
-------------

https://github.com/seporaitis/yum-s3-iam

https://wiki.jenkins-ci.org/display/JENKINS/S3+Plugin

