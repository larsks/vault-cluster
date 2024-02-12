%.yaml: %.jsonnet
	jsonnet -o $@ $<

all: compose.yaml

