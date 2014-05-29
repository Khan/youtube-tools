import unittest

import add_ka_links


class DescriptionAnnotationTest(unittest.TestCase):
    def test_double_annotation(self):
        url = 'http://www.khanacademy.org/video?v=2aUFB9hQncQ'

        desc = 'Two worked examples of solving simple equations'
        desc2 = add_ka_links.annotate_description(desc, 'www', url)
        self.assertIn(url, desc2)
        desc3 = add_ka_links.annotate_description(desc2, 'www', url)
        self.assertEqual(desc2, desc3)

        # Empty description
        desc = None
        desc2 = add_ka_links.annotate_description(desc, 'www', url)
        self.assertIn(url, desc2)
        desc3 = add_ka_links.annotate_description(desc2, 'www', url)
        self.assertEqual(desc2, desc3)

    def test_unannotation(self):
        desc = ("Learn more: "
                "http://www.khanacademy.org/video?v=2aUFB9hQncQ\n"
                "Monet's Cliff Walk")
        desc2 = add_ka_links.unannotate_description(desc)
        self.assertEqual("Monet's Cliff Walk", desc2)

        desc = ("Mais aulas gratuitas em: "
                "http://pt.khanacademy.org/video?v=2aUFB9hQncQ\n"
                "Monet's Cliff Walk")
        desc2 = add_ka_links.unannotate_description(desc)
        self.assertEqual("Monet's Cliff Walk", desc2)


if __name__ == '__main__':
    unittest.main()
