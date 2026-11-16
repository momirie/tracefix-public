## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the original datetime bin-edge error but found that the fix breaks about 75 previously passing tests, spanning the matplotlib line backend, plot, slicer, superplot, figline and high-level tests, and no test guards the reported bug. Start with tests/backends/matplotlib/mpl\_line\_test.py::test\_line\_creation and test\_line\_with\_errorbars, since the change appears to break basic…

**Why this level:** regression: tests/backends/matplotlib/mpl\_figline\_test.py::test\_with\_string\_coord passed before the fix and fails after it; regression: tests/backends/matplotlib/mpl\_figline\_test.py::test\_with\_strings\_as\_bin\_edges passed before the fix and fails after it; regression: tests/backends/matplotlib/mpl\_figline\_test.py::test\_figsize passed before the fix and fails after it; regression: tests/backends/matplotlib/mpl\_figline\_test.py::test\_grid passed before the fix and fails after it; regression: tests/backends/matplotlib/mpl\_figline\_test.py::test\_ax passed before the fix and fails after it; regression: tests/backends/matplotlib/mpl\_interactive\_test.py::test\_logx\_1d\_toolbar\_button passed before the fix and fails after it; and 68 more in receipt.json

**Issue:** Cannot make 1d plot for data with datetime coord and variances · **Repo:** testbed · **Base** `tf-base` (`df3a5f2`) → **head** `tf-v2` (`ff238f6`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples (5 of 74; the rest in receipt.json)
1. Regression: `tests/backends/matplotlib/mpl_figline_test.py::test_with_string_coord` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
2. Regression: `tests/backends/matplotlib/mpl_figline_test.py::test_with_strings_as_bin_edges` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
3. Regression: `tests/backends/matplotlib/mpl_figline_test.py::test_figsize` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
4. Regression: `tests/backends/matplotlib/mpl_figline_test.py::test_grid` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
5. Regression: `tests/backends/matplotlib/mpl_figline_test.py::test_ax` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 2 |
| `reproduce` | `reproduced` | attempts 3 |
| `guard` | `not_guarded` | kill rate 0\.0, mutants 9, killed 0, survived 9 |
| `regressions` | `found` | compared 245, regressions 74, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 77 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 6, inputs tried 0, properties counted 11, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 19; the rest in receipt.json)
- `src/plopp/backends/plotly/line.py:195`: `             y = sc.concat([y[0:1], y], dim=self._dim) ` → `             y = sc.concat([y[-1:], y], dim=self._dim) ` made no test fail; not compared with the fix (`m-28611a0a20ef`)
- `src/plopp/backends/plotly/line.py:197`: `                 mask['y'] = np.concatenate([mask['y'][0:1], ... ` → `                 mask['y'] = np.concatenate([mask['y'][0:1], ... ` made no test fail; not compared with the fix (`m-d6005097f372`)
- `src/plopp/backends/plotly/line.py:183`: `             'x': sc.midpoints(x).values if hist else x.values, ` → `             'x': x.values if hist else sc.midpoints(x).values, ` made no test fail; not compared with the fix (`m-7318aaebf6ad`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 8 calls, 110,316 input and 8,557 output tokens, cost $0.4708 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 23.41 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 5.59 s: 2 changed module(s) imported from the copies (4 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 78.61 s: attempt 3: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/back...`
- `guard`: `not_guarded`, 771.86 s: the tests killed 0 of 9 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/back...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `found`, 119.66 s: 74 confirmed: tests/backends/matplotlib/mpl\_figline\_test.py::test\_with\_string\_coord, tests/backends/matplotlib/mpl\_figline\_test.py::test\_with\_strings\_as\_bin\_edges, tests/backends/matplotlib/mpl\_figline\_test.py::test\_figsize, tests/backends/matplotlib/mpl\_figline\_test.py::test\_grid, tests/backends/matplotlib/mpl\_figline\_test.py::test\_ax and 69 more
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 3.56 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/back...`
- `behaviour_diff`: `inconclusive`, 5.18 s: nothing was compared: Line.update: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `inconclusive`, 66.3 s: the attack ran no input
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
#### More counterexamples
- Regression: `tests/backends/matplotlib/mpl_interactive_test.py::test_logx_1d_toolbar_button` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/backends/matplotlib/mpl_interactive_test.py::test_logy_1d_toolbar_button` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/backends/matplotlib/mpl_line_test.py::test_line_creation` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/backends/matplotlib/mpl_line_test.py::test_line_creation_bin_edges` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/backends/matplotlib/mpl_line_test.py::test_line_with_errorbars` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/backends/matplotlib/mpl_line_test.py::test_line_hide_errorbars` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/backends/matplotlib/mpl_line_test.py::test_line_with_mask` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/backends/matplotlib/mpl_line_test.py::test_line_update` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/backends/matplotlib/mpl_line_test.py::test_line_update_with_errorbars` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_plot_ndarray` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_plot_variable` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_plot_data_array` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_plot_data_array_missing_coords` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_plot_dataset` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_plot_dict_of_ndarrays` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_plot_dict_of_variables` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_plot_dict_of_data_arrays` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_plot_coord_with_no_unit` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_plot_ignore_size_disables_size_check` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_kwarg_linecolor` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_kwarg_linestyle` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_kwarg_linewidth` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_kwarg_marker` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_kwarg_norm` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_kwarg_scale` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_kwarg_crop_1d_min_max` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_kwarg_crop_1d_min_only` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_kwarg_crop_1d_min_conversion` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_kwarg_crop_1d_with_no_unit` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_kwarg_for_two_lines` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_kwarg_as_dict` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_use_non_dimension_coords_dataset` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_save_to_disk_1d[jpg]` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_save_to_disk_1d[pdf]` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_save_to_disk_1d[png]` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/plot_test.py::test_save_to_disk_1d[svg]` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/slicer_test.py::test_creation_keep_one_dim` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/slicer_test.py::test_update_keep_one_dim` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/slicer_test.py::test_with_dataset` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/slicer_test.py::test_with_dict_of_data_arrays` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/superplot_test.py::test_creation` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/superplot_test.py::test_save_line` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/superplot_test.py::test_remove_line` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/functions/superplot_test.py::test_change_line_color` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_update` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_create_with_node` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_with_errorbars` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_with_binedges` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_crop` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_crop_no_variable` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_update_grows_limits` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_update_does_not_shrink_limits` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_vmin` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_vmin_unit_mismatch_raises` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_vmax` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_vmin_vmax` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_vmin_vmax_no_variable` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_raises_for_new_data_with_incompatible_dimension` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_raises_for_new_data_with_incompatible_unit` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_raises_for_new_data_with_incompatible_coord_unit` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_converts_new_data_units` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_converts_new_data_coordinate_units` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/graphics/figline_test.py::test_converts_new_data_units_integers` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/high_level_test.py::test_single_1d_line` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/high_level_test.py::test_two_1d_lines` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/high_level_test.py::test_difference_of_two_1d_lines` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/high_level_test.py::test_two_1d_lines_with_masks` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/high_level_test.py::test_node_sum_data_along_y` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
- Regression: `tests/high_level_test.py::test_3d_image_slicer_with_connected_side_histograms` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'mask\_data\_key' is not defined)
#### Break My Fix targets
- `plopp.backends.matplotlib.line.Line.update` (`src/plopp/backends/matplotlib/line.py`): 0 inputs
- `plopp.backends.plotly.line.Line.update` (`src/plopp/backends/plotly/line.py`): 0 inputs
- `plopp.backends.matplotlib.line.Line._make_line` (`src/plopp/backends/matplotlib/line.py`): 0 inputs
- `plopp.backends.matplotlib.line.Line._make_data` (`src/plopp/backends/matplotlib/line.py`): 0 inputs
- `plopp.backends.plotly.line.Line._make_line` (`src/plopp/backends/plotly/line.py`): 0 inputs
- `plopp.backends.plotly.line.Line._make_data` (`src/plopp/backends/plotly/line.py`): 0 inputs
#### More changes no test noticed
- `src/plopp/backends/plotly/line.py:178`: `         hist = len(x) != len(y) ` → `         hist = len(x) > len(y) + 1 ` made no test fail; not compared with the fix (`m-73d041cb3a9f`)
- `src/plopp/backends/plotly/line.py:191`: `                 'y': np.where(one_mask, y.values, np.nan), ` → `                 'y': np.where(one_mask, np.nan, y.values), ` made no test fail; not compared with the fix (`m-59dfe813a28d`)
- `src/plopp/backends/matplotlib/line.py:178`: `                 'y': np.where(one_mask, y.values, np.nan), ` → `                 'y': np.where(one_mask, np.nan, y.values), ` made no test fail; not compared with the fix (`m-ed32d9f70a95`)
- `src/plopp/backends/matplotlib/line.py:182`: `             y = sc.concat([y[0:1], y], dim=self._dim) ` → `             y = sc.concat([y[-1:], y], dim=self._dim) ` made no test fail; not compared with the fix (`m-f7bf27a83c90`)
- `src/plopp/backends/matplotlib/line.py:184`: `                 mask['y'] = np.concatenate([mask['y'][0:1], ... ` → `                 mask['y'] = np.concatenate([mask['y'], mask[... ` made no test fail; not compared with the fix (`m-be023d779ccd`)
- `src/plopp/backends/plotly/line.py:236`: `                 update = {'x': new_values['mask']['x'], 'y':... ` → `                 update = {'x': new_values['values']['x'], 'y... ` made no test fail; not compared with the fix (`m-5de879779ebc`)
- `src/plopp/backends/matplotlib/line.py:101`: `         default_step_style = {\n            'linestyle': 'sol... ` → `         return None ` made no test fail; not compared with the fix (`m-2a6dc4e2a7f2`)
- `src/plopp/backends/matplotlib/line.py:163`: `         x = self._data.meta[self._dim]\n        y = self._dat... ` → `         return {} ` made no test fail; not compared with the fix (`m-6eec61577e0c`)
- `src/plopp/backends/matplotlib/line.py:204`: `         self._data = new_values\n        new_values = self._m... ` → `         return None ` made no test fail; not compared with the fix (`m-b6b823cde08c`)
- 32 more line(s) in receipt.json

</details>
