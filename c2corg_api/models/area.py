from c2corg_api.models import schema
from c2corg_api.models.document import (
    ArchiveDocument, Document, get_update_schema, geometry_schema_overrides,
    schema_document_locale, schema_attributes)
from c2corg_api.models.enums import area_type
from c2corg_api.models.schema_utils import restrict_schema
from c2corg_api.models.utils import copy_attributes
from c2corg_common.fields_area import fields_area
from colanderalchemy import SQLAlchemySchemaNode
from sqlalchemy import (
    Column,
    Integer,
    ForeignKey
    )

AREA_TYPE = 'a'


class _AreaMixin(object):
    area_type = Column(area_type)

    __mapper_args__ = {
        'polymorphic_identity': AREA_TYPE
    }

attributes = ['area_type']


class Area(_AreaMixin, Document):
    """
    """
    __tablename__ = 'areas'

    document_id = Column(
        Integer,
        ForeignKey(schema + '.documents.document_id'), primary_key=True)

    def to_archive(self):
        area = ArchiveArea()
        super(Area, self)._to_archive(area)
        copy_attributes(self, area, attributes)

        return area

    def update(self, other):
        super(Area, self).update(other)
        copy_attributes(other, self, attributes)


class ArchiveArea(_AreaMixin, ArchiveDocument):
    """
    """
    __tablename__ = 'areas_archives'

    id = Column(
        Integer,
        ForeignKey(schema + '.documents_archives.id'), primary_key=True)


schema_area = SQLAlchemySchemaNode(
    Area,
    # whitelisted attributes
    includes=schema_attributes + attributes,
    overrides={
        'document_id': {
            'missing': None
        },
        'version': {
            'missing': None
        },
        'locales': {
            'children': [schema_document_locale]
        },
        'geometry': geometry_schema_overrides
    })

schema_update_area = get_update_schema(schema_area)
schema_listing_area = restrict_schema(
    schema_area, fields_area.get('listing'))
