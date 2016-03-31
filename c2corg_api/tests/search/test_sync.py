import transaction

from c2corg_api.models.document import DocumentGeometry
from c2corg_api.models.waypoint import Waypoint, WaypointLocale
from c2corg_api.search import elasticsearch_config
from c2corg_api.search.mappings.waypoint_mapping import SearchWaypoint
from c2corg_api.search.sync import sync_search_index
from c2corg_api.tests import BaseTestCase


class SyncTest(BaseTestCase):

    def test_sync_search_index_insert(self):
        """Tests that new documents are inserted in the index.
        """
        index = elasticsearch_config['index']
        waypoint = Waypoint(
            document_id=51251,
            waypoint_type='summit', elevation=2000,
            geometry=DocumentGeometry(
                geom='SRID=3857;POINT(635956 5723604)'),
            locales=[
                WaypointLocale(
                    lang='fr', title='Mont Granier',
                    description='...',
                    summary='Le Mont [b]Granier[/b]')
            ])

        t = transaction.begin()
        sync_search_index(waypoint)
        t.commit()

        doc = SearchWaypoint.get(id=51251, index=index)
        self.assertEqual(doc['title_fr'], 'Mont Granier')
        self.assertEqual(doc['summary_fr'], 'Le Mont  Granier ')
        self.assertEqual(doc['doc_type'], 'w')

    def test_sync_search_index_update(self):
        """Tests that already existing documents are updated.
        """
        index = elasticsearch_config['index']
        waypoint = Waypoint(
            document_id=51252,
            waypoint_type='summit', elevation=2000,
            geometry=DocumentGeometry(
                geom='SRID=3857;POINT(635956 5723604)'),
            locales=[
                WaypointLocale(
                    lang='fr', title='Mont Granier',
                    description='...',
                    summary='Le Mont Granier')
            ])

        # insert the document
        t = transaction.begin()
        sync_search_index(waypoint)
        t.commit()

        # then update the document (add a new language)
        waypoint = Waypoint(
            document_id=51252,
            waypoint_type='summit', elevation=2000,
            geometry=DocumentGeometry(
                geom='SRID=3857;POINT(635956 5723604)'),
            locales=[
                WaypointLocale(
                    lang='fr', title='Mont Granier',
                    description='...',
                    summary='Le Mont Granier'),
                WaypointLocale(
                    lang='en', title='Mont Granier',
                    description='...',
                    summary='The Mont Granier')
            ])

        t = transaction.begin()
        sync_search_index(waypoint)
        t.commit()

        doc = SearchWaypoint.get(id=51252, index=index)
        self.assertEqual(doc['title_fr'], 'Mont Granier')
        self.assertEqual(doc['summary_fr'], 'Le Mont Granier')
        self.assertEqual(doc['title_en'], 'Mont Granier')
        self.assertEqual(doc['summary_en'], 'The Mont Granier')
        self.assertEqual(doc['doc_type'], 'w')

    def test_sync_search_index_merged_document(self):
        """Tests that merged documents are removed from the search index.
        """
        index = elasticsearch_config['index']
        waypoint = Waypoint(
            document_id=51251,
            waypoint_type='summit', elevation=2000,
            geometry=DocumentGeometry(
                geom='SRID=3857;POINT(635956 5723604)'),
            locales=[
                WaypointLocale(
                    lang='fr', title='Mont Granier',
                    description='...',
                    summary='Le Mont [b]Granier[/b]')
            ])

        # first insert the document
        t = transaction.begin()
        sync_search_index(waypoint)
        t.commit()

        self.assertIsNotNone(SearchWaypoint.get(id=51251, index=index))

        # then set `redirects_to` and sync again
        waypoint.redirects_to = 51252

        t = transaction.begin()
        sync_search_index(waypoint)
        t.commit()

        # check that the document is removed
        self.assertIsNone(SearchWaypoint.get(id=51251, ignore=404))

        # now sync a 2nd time to check that already deleted documents are not
        # a problem

        t = transaction.begin()
        sync_search_index(waypoint)
        t.commit()

        # check that the document is removed
        self.assertIsNone(SearchWaypoint.get(id=51251, ignore=404))
