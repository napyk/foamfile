File parser for OpenFOAM configuration files based on <https://cfd.direct/openfoam/user-guide/v6-basic-file-format/>

foamfile uses [pyparsing](https://github.com/pyparsing/pyparsing/) to extract the data from the files.

### example usage
```python
from foamfile import FoamFile

with FoamFile("path/to/file") as f:
    foam_content = f.read()
    print(f.header)
    print(foam_content)

with FoamFile("path/to/file", "w", foam_class="dictionary") as f:
    f.write(foam_content)
```

### TODO
* Macro expansion does not work at the moment
* Optimize parsing of directives
* Add codeStreams
* Add calculations
* Add support for comments

Tested with OpenFOAM v6.
