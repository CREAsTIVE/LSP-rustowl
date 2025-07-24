# LSP-rustowl plugin

This plugin will add [rustowl](https://github.com/cordx56/rustowl) support to Sublime Text using sublime [LSP](https://github.com/sublimelsp/LSP)

## Usage

That plugin will automaticly show lifetime of an variable at your'e cursor position. You can also configure it to use mouse position, or none.

#### Commands

If you set property `rustowl.hover_type` to `"none"`, you can use next commands at command pallete (`ctrl + shift + p`):

* `Rustowl: Analyze lifetime`
  Analyzes lifetime of variable at current cursor position
* `Rustowl: Clear`
  Clears all lifetime highliting on current view

## Configuration

To configure that plugin open commande pallete (`ctrl + shift + p`) and enter `Preferences: LSP-rustowl Settings`

## Manual Installation

Clone [LSP repository](https://github.com/sublimelsp/LSP) and [this repository](https://github.com/CREAsTIVE/LSP-rustowl) into your'e sublime `Package` folder. 

## Instalation (CURRENTLY UNAVAILABLE IN PACKAGE CONTROL, SEE [#1](https://github.com/CREAsTIVE/LSP-rustowl/issues/1))

* Install `LSP` plugin from package control

* Install `LSP-rustowl` plugin from package control

* Restart Sublime
