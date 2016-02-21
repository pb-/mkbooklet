from unittest import TestCase
from mock import patch

from ..boundingbox import median_bbox, extrema_bbox


class BoundingboxTest(TestCase):
    @patch('mkbooklet.boundingbox.bounding_boxes')
    def test_median_bbox(self, bboxes):
        bboxes.return_value = [
            (5, 3, 104, 109),
            (4, 9, 100, 101),
            (8, 2, 108, 103),
        ]

        self.assertEqual(median_bbox(None), (5, 3, 104, 103))

    @patch('mkbooklet.boundingbox.bounding_boxes')
    def test_extrema_bbox(self, bboxes):
        bboxes.return_value = [
            (5, 3, 104, 109),
            (4, 9, 100, 101),
            (8, 2, 108, 103),
        ]

        self.assertEqual(extrema_bbox(None), (4, 2, 108, 109))
