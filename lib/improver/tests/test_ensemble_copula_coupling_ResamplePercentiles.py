# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# (C) British Crown Copyright 2017 Met Office.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""
Unit tests for the `ensemble_copula_coupling.ResamplePercentiles` class.
"""
import numpy as np
import unittest

from cf_units import Unit
from iris.coords import AuxCoord, DimCoord
from iris.cube import Cube
from iris.tests import IrisTest

from improver.ensemble_copula_coupling.ensemble_copula_coupling import (
    ResamplePercentiles as Plugin)
from improver.ensemble_copula_coupling.ensemble_copula_coupling_constants \
    import bounds_for_ecdf
from improver.tests.helper_functions_ensemble_calibration import(
    _add_forecast_reference_time_and_forecast_period,
    set_up_cube, set_up_temperature_cube, set_up_spot_cube,
    set_up_spot_temperature_cube)


class Test__add_bounds_to_percentiles_and_forecast_values(IrisTest):

    """
    Test the _add_bounds_to_percentiles_and_forecast_values method of the
    ResamplePercentiles plugin.
    """

    def setUp(self):
        data = np.tile(np.linspace(5, 10, 9), 3).reshape(3, 1, 3, 3)
        data[0] -= 1
        data[1] += 1
        data[2] += 3
        cube = set_up_cube(data, "air_temperature", "degreesC")
        self.realization_cube = (
            _add_forecast_reference_time_and_forecast_period(cube.copy()))
        cube.coord("realization").rename("percentile")
        cube.coord("percentile").points = np.array([0.1, 0.5, 0.9])
        self.percentile_cube = (
            _add_forecast_reference_time_and_forecast_period(cube))

    def test_basic(self):
        """Test that the plugin returns two numpy arrays."""
        cube = self.percentile_cube
        percentiles = cube.coord("percentile").points
        forecast_at_percentiles = cube.data.reshape(3, 9)
        bounds_pairing = (-40, 50)
        plugin = Plugin()
        result = plugin._add_bounds_to_percentiles_and_forecast_at_percentiles(
            percentiles, forecast_at_percentiles, bounds_pairing)
        self.assertIsInstance(result[0], np.ndarray)
        self.assertIsInstance(result[1], np.ndarray)

    def test_bounds_of_percentiles(self):
        """
        Test that the plugin returns the expected results for the
        percentiles, where the percentile values have been padded with 0 and 1.
        """
        cube = self.percentile_cube
        percentiles = cube.coord("percentile").points
        forecast_at_percentiles = cube.data.reshape(3, 9)
        bounds_pairing = (-40, 50)
        plugin = Plugin()
        result = plugin._add_bounds_to_percentiles_and_forecast_at_percentiles(
            percentiles, forecast_at_percentiles, bounds_pairing)
        self.assertArrayAlmostEqual(result[0][0], 0)
        self.assertArrayAlmostEqual(result[0][-1], 1)

    def test_probability_data(self):
        """
        Test that the plugin returns the expected results for the
        forecast values, where they've been padded with the values from the
        bounds_pairing.
        """
        cube = self.percentile_cube
        percentiles = cube.coord("percentile").points
        forecast_at_percentiles = cube.data.reshape(3, 9)
        bounds_pairing = (-40, 50)
        lower_array = np.full(
            forecast_at_percentiles[:, 0].shape, bounds_pairing[0])
        upper_array = np.full(
            forecast_at_percentiles[:, 0].shape, bounds_pairing[1])
        plugin = Plugin()
        result = plugin._add_bounds_to_percentiles_and_forecast_at_percentiles(
            percentiles, forecast_at_percentiles, bounds_pairing)
        self.assertArrayAlmostEqual(result[1][:, 0], lower_array)
        self.assertArrayAlmostEqual(result[1][:, -1], upper_array)

    def test_endpoints_of_distribution_exceeded(self):
        """
        Test that the plugin raises a ValueError when the constant
        end points of the distribution are exceeded by a forecast value.
        The end points must be outside the minimum and maximum within the
        forecast values.
        """
        forecast_at_percentiles = np.array([[8, 10, 60]])
        percentiles = np.array([0.05, 0.7, 0.95])
        bounds_pairing = (-40, 50)
        plugin = Plugin()
        msg = "The end points added to the forecast at percentiles"
        with self.assertRaisesRegexp(ValueError, msg):
            plugin._add_bounds_to_percentiles_and_forecast_at_percentiles(
                percentiles, forecast_at_percentiles, bounds_pairing)

    def test_percentiles_not_ascending(self):
        """
        Test that the plugin raises a ValueError, if the percentiles are
        not in ascending order.
        """
        forecast_at_percentiles = np.array([[8, 10, 12]])
        percentiles = np.array([100, 0, -100])
        bounds_pairing = (-40, 50)
        plugin = Plugin()
        msg = "The percentiles must be in ascending order"
        with self.assertRaisesRegexp(ValueError, msg):
            plugin._add_bounds_to_percentiles_and_forecast_at_percentiles(
                percentiles, forecast_at_percentiles, bounds_pairing)


class Test__sample_percentiles(IrisTest):

    """
    Test the _sample_percentiles method of the ResamplePercentiles plugin.
    """

    def setUp(self):
        data = np.tile(np.linspace(5, 10, 9), 3).reshape(3, 1, 3, 3)
        data[0] -= 1
        data[1] += 1
        data[2] += 3
        cube = set_up_cube(data, "air_temperature", "degreesC")
        cube.coord("realization").rename("percentile")
        cube.coord("percentile").points = np.array([0.1, 0.5, 0.9])
        self.percentile_cube = (
            _add_forecast_reference_time_and_forecast_period(cube))
        spot_cube = (
            _add_forecast_reference_time_and_forecast_period(
                set_up_spot_temperature_cube()))
        spot_cube.convert_units("degreesC")
        spot_cube.coord("realization").rename("percentile")
        spot_cube.coord("percentile").points = np.array([0.1, 0.5, 0.9])
        spot_cube.data = np.tile(np.linspace(5, 10, 3), 9).reshape(3, 1, 9)
        self.spot_percentile_cube = spot_cube

    def test_basic(self):
        """Test that the plugin returns an Iris.cube.Cube."""
        cube = self.percentile_cube
        percentiles = [0.1, 0.5, 0.9]
        bounds_pairing = (-40, 50)
        plugin = Plugin()
        result = plugin._sample_percentiles(
            cube, percentiles, bounds_pairing)
        self.assertIsInstance(result, Cube)

    def test_simple_check_data(self):
        """
        Test that the plugin returns an Iris.cube.Cube with the expected
        forecast values at each percentile.
        """
        expected = np.array([8, 10, 12])
        expected = expected[:, np.newaxis, np.newaxis, np.newaxis]

        data = np.array([8, 10, 12])
        data = data[:, np.newaxis, np.newaxis, np.newaxis]

        current_temperature_forecast_cube = (
            _add_forecast_reference_time_and_forecast_period(
                set_up_cube(
                    data, "air_temperature", "1",
                    y_dimension_length=1, x_dimension_length=1)))
        cube = current_temperature_forecast_cube
        cube.coord("realization").rename("percentile")
        cube.coord("percentile").points = np.array([0.1, 0.5, 0.9])
        percentiles = [0.1, 0.5, 0.9]
        bounds_pairing = (-40, 50)
        plugin = Plugin()
        result = plugin._sample_percentiles(
            cube, percentiles, bounds_pairing)
        self.assertArrayAlmostEqual(result.data, expected)

    def test_check_data(self):
        """
        Test that the plugin returns an Iris.cube.Cube with the expected
        data values for the percentiles.
        """
        data = np.array([[[[4.5, 6.5, 7.5],
                           [5.125, 7.125, 8.125],
                           [5.75, 7.75, 8.75]]],
                         [[[6.375, 8.375, 9.375],
                           [7., 9., 10.],
                           [7.625, 9.625, 10.625]]],
                         [[[8.25, 10.25, 11.25],
                           [8.875, 10.875, 11.875],
                           [9.5, 11.5, 12.5]]]])

        cube = self.percentile_cube
        percentiles = [0.2, 0.6, 0.8]
        bounds_pairing = (-40, 50)
        plugin = Plugin()
        result = plugin._sample_percentiles(
            cube, percentiles, bounds_pairing)
        self.assertArrayAlmostEqual(result.data, data)

    def test_check_single_threshold(self):
        """
        Test that the plugin returns an Iris.cube.Cube with the expected
        data values for the percentiles, if a single percentile is used within
        the input set of percentiles.
        """
        expected = np.array([[[[4., 24.44444444, 44.88888889],
                               [4.625, 24.79166667, 44.95833333],
                               [5.25, 25.13888889, 45.02777778]]],
                             [[[5.875, 25.48611111, 45.09722222],
                               [6.5, 25.83333333, 45.16666667],
                               [7.125, 26.18055556, 45.23611111]]],
                             [[[7.75, 26.52777778, 45.30555556],
                               [8.375, 26.875, 45.375],
                               [9., 27.22222222, 45.44444444]]]])

        data = np.array([8])
        data = data[:, np.newaxis, np.newaxis, np.newaxis]

        current_temperature_forecast_cube = (
            _add_forecast_reference_time_and_forecast_period(
                set_up_cube(
                    data, "air_temperature", "1",
                    realizations=[0],
                    y_dimension_length=1, x_dimension_length=1)))
        cube = current_temperature_forecast_cube
        cube.coord("realization").rename("percentile")
        cube.coord("percentile").points = np.array([0.2])

        for acube in self.percentile_cube.slices_over("percentile"):
            cube = acube
            break
        percentiles = [0.1, 0.5, 0.9]
        bounds_pairing = (-40, 50)
        plugin = Plugin()
        result = plugin._sample_percentiles(
            cube, percentiles, bounds_pairing)
        self.assertArrayAlmostEqual(result.data, expected)

    def test_lots_of_input_percentiles(self):
        """
        Test that the plugin returns an Iris.cube.Cube with the expected
        data values for the percentiles, if there are lots of thresholds.
        """
        input_forecast_values_1d = np.linspace(10, 20, 30)
        input_forecast_values = np.tile(input_forecast_values_1d, (3, 3, 1, 1)).T
        #print "input_percentiles = ", input_percentiles

        data = np.array([[[[11., 15., 19.],
                           [11., 15., 19.],
                           [11., 15., 19.]]],
                         [[[11., 15., 19.],
                           [11., 15., 19.],
                           [11., 15., 19.]]],
                         [[[11., 15., 19.],
                           [11., 15., 19.],
                           [11., 15., 19.]]]])

        percentiles_values = np.linspace(0, 1, 30)
        cube = (
            _add_forecast_reference_time_and_forecast_period(
                set_up_cube(input_forecast_values, "air_temperature", "1",
                            realizations=np.arange(30))))
        cube.coord("realization").rename("percentile")
        cube.coord("percentile").points = np.array(percentiles_values)
        percentiles = [0.1, 0.5, 0.9]
        bounds_pairing = (-40, 50)
        plugin = Plugin()
        result = plugin._sample_percentiles(
            cube, percentiles, bounds_pairing)
        self.assertArrayAlmostEqual(result.data, data)

    def test_lots_of_percentiles(self):
        """
        Test that the plugin returns an Iris.cube.Cube with the expected
        data values for the percentiles, if lots of percentile values are
        requested.
        """
        data = np.array([[[[-18., 4.25, 4.75],
                           [5.25, 5.75, 6.25],
                           [6.75, 7.25, 7.75]]],
                         [[[29., -17.6875, 4.875],
                           [5.375, 5.875, 6.375],
                           [6.875, 7.375, 7.875]]],
                         [[[8.375, 29.3125, -17.375],
                           [5.5, 6., 6.5],
                           [7., 7.5, 8.]]],
                         [[[8.5, 9., 29.625],
                           [-17.0625, 6.125, 6.625],
                           [7.125, 7.625, 8.125]]],
                         [[[8.625, 9.125, 9.625],
                           [29.9375, -16.75, 6.75],
                           [7.25, 7.75, 8.25]]],
                         [[[8.75, 9.25, 9.75],
                           [10.25, 30.25, -16.4375],
                           [7.375, 7.875, 8.375]]],
                         [[[8.875, 9.375, 9.875],
                           [10.375, 10.875, 30.5625],
                           [-16.125, 8., 8.5]]],
                         [[[9., 9.5, 10.],
                           [10.5, 11., 11.5],
                           [30.875, -15.8125, 8.625]]],
                         [[[9.125, 9.625, 10.125],
                           [10.625, 11.125, 11.625],
                           [12.125, 31.1875, -15.5]]],
                         [[[9.25, 9.75, 10.25],
                           [10.75, 11.25, 11.75],
                           [12.25, 12.75, 31.5]]]])
        cube = self.percentile_cube
        percentiles = np.arange(0.05, 1.0, 0.1)
        bounds_pairing = (-40, 50)
        plugin = Plugin()
        result = plugin._sample_percentiles(
            cube, percentiles, bounds_pairing)
        self.assertArrayAlmostEqual(result.data, data)

    def test_check_data_spot_forecasts(self):
        """
        Test that the plugin returns an Iris.cube.Cube with the expected
        data values for the percentiles for spot forecasts.
        """
        data = np.array([[[5., 5., 5., 7.5, 7.5, 7.5, 10., 10., 10.]],
                         [[5., 5., 5., 7.5, 7.5, 7.5, 10., 10., 10.]],
                         [[5., 5., 5., 7.5, 7.5, 7.5, 10., 10., 10.]]])
        cube = self.spot_percentile_cube
        percentiles = [0.1, 0.5, 0.9]
        bounds_pairing = (-40, 50)
        plugin = Plugin()
        result = plugin._sample_percentiles(
            cube, percentiles, bounds_pairing)
        self.assertArrayAlmostEqual(result.data, data)


class Test_process(IrisTest):

    """Test the process plugin of the Resample Percentiles plugin."""

    def setUp(self):
        data = np.tile(np.linspace(5, 10, 9), 3).reshape(3, 1, 3, 3)
        data[0] -= 1
        data[1] += 1
        data[2] += 3
        cube = set_up_cube(data, "air_temperature", "degreesC")
        cube.coord("realization").rename("percentile")
        cube.coord("percentile").points = np.array([0.1, 0.5, 0.9])
        self.percentile_cube = (
            _add_forecast_reference_time_and_forecast_period(cube))

    def test_check_data_specifying_percentiles(self):
        """
        Test that the plugin returns an Iris.cube.Cube with the expected
        data values for a specific number of percentiles.
        """
        data = np.array([[[[4.75, 6., 7.25],
                          [5.375, 6.625, 7.875],
                          [6., 7.25, 8.5]]],
                        [[[6.625, 7.875, 9.125],
                          [7.25, 8.5, 9.75],
                          [7.875, 9.125, 10.375]]],
                        [[[8.5, 9.75, 11.],
                          [9.125, 10.375, 11.625],
                          [9.75, 11., 12.25]]]])

        cube = self.percentile_cube
        percentiles = [0.25, 0.5, 0.75]
        plugin = Plugin()
        result = plugin.process(cube, no_of_percentiles=len(percentiles))
        self.assertArrayAlmostEqual(result.data, data)

    def test_check_data_not_specifying_percentiles(self):
        """
        Test that the plugin returns an Iris.cube.Cube with the expected
        data values without specifying the number of percentiles.
        """
        data = np.array([[[[4.75, 6., 7.25],
                          [5.375, 6.625, 7.875],
                          [6., 7.25, 8.5]]],
                        [[[6.625, 7.875, 9.125],
                          [7.25, 8.5, 9.75],
                          [7.875, 9.125, 10.375]]],
                        [[[8.5, 9.75, 11.],
                          [9.125, 10.375, 11.625],
                          [9.75, 11., 12.25]]]])

        cube = self.percentile_cube
        plugin = Plugin()
        result = plugin.process(cube)
        self.assertArrayAlmostEqual(result.data, data)


if __name__ == '__main__':
    unittest.main()