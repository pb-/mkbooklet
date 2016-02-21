from unittest import TestCase

from ..signature import format_signatures_sequence as fmt

class SignatureTest(TestCase):
    def test(self):
        self.assertEqual(fmt(1, 1), '{},1,{},{}')
        self.assertEqual(fmt(2, 1), '{},1,2,{}')
        self.assertEqual(fmt(3, 1), '{},1,2,3')
        self.assertEqual(fmt(4, 1), '4,1,2,3')

        self.assertEqual(fmt(7, 2), '{},1,2,7,6,3,4,5')

        self.assertEqual(fmt(7, 1), '4,1,2,3,{},5,6,7')
