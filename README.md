# CAD Conversion

This repo contains source code for an application running PyQt5 and based on PythonOCC.

## Installation

1. Clone the repository: 
```bash
1. git clone https://github.com/martinorrje/CADConversion.git
```
2. Navigate to the repository:
```bash
cd CADConversion
```
3. If you don't have Conda installed, you'll need to [install it](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html) first.
4. Create a Conda environment using the `environment.yml` file included in the repository:
```bash
conda env create -f environment.yml
```
5. Activate the conda environment: 
````bash
conda activate CADConversionGUI
````

## Usage

Run the application using:
1. If the environment is not already active, activate the Conda environment:
```bash
conda activate CADConversionGUI
```
2. Run `main.py`:
```bash
python3 main.py
```

NOTE: If you get error messages complaining about not finding `graphviz` module, try installing it manually with 
```bash
conda install -c conda-forge python-graphviz
```

## Example
In the examples folder are two files: `spider.json` and `slider_crank.json`. These have been created from the CADConversion program,
and contains models with joints and materials associated with them. 

### Generate graph from model
To generate a JSON file containing physical properties for each component and joint, navigate to the menu bar and select Export->Export linear graph. You will be prompted to select the folder where a data.json file will be saved, together with two png images for a visualization of the rotation graph and the translation graph. 

### Create joint
To create a joint, select Joints->Add joint in the menu bar. A widget will appear in the right part of the screen. Here you can select the two components belonging to the joint by pressing the corresponding "Select component" button, hovering over the component you want to select and clicking to select. To select a joint origin for the joint, press the "Select joint origin" button and navigate your mouse pointer to the desired joint origin. A trihedron will appear at the mouse, which snaps to geometric features such as faces, vertices, edges and circular features. 

### Assign material
To assign material to a component, select one or several components in the Assembly/Part Structure view at the left part of the screen, and then right-click with the mouse pointer still over the "Assembly/Part Structure" widget, and select the "Change material" option from the pop-up menu. You now have three options: 
* Select a predefined material, from which the density and mass of the component will be calculated
* Select a custom mass for the component
* Select a custom density for the component

### Geometric editing

#### Delete components
The program provides basic features for geometric editing. To delete components, select the components you want to delete in the "Assembly/Part Structure" view to the left, right-click with the mouse pointer still over the "Assembly/Part Structure" widget, and select "Delete Components". 

#### Combine components
To combine components, select the components you want to combine in the "Assembly/Part Structure" widget to the left, right-click (with the mouse still over the "Assembly/Part Structure" widget), and select "Combine components".

### Other functions

#### Rename components
To rename a component, simply double-click on its name in the "Assembly/Part Structure" widget to the left, write a new name and then press enter.




