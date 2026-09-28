.PHONY: data test

data:
	aws s3 cp s3://data-bucket/mnist data/raw --recursive

test:
	pytest
