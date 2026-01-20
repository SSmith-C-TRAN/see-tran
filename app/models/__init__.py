# Example model - create more files in app/models/ as needed
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String
from app import db

# Import existing models
from .tran import (
    Agency, FunctionalArea, Vendor, Component, Function,
    IntegrationPoint, UserRole, UpdateLog, Standard, TagGroup, Tag,
    User, VerifiedAgencyDomain
)

# Import GTFS models
from .gtfs import (
    GTFSAgency, GTFSStop, GTFSRoute, GTFSCalendar, GTFSCalendarDate,
    GTFSTrip, GTFSStopTime, GTFSShape, GTFSFeedInfo,
    GTFSFareMedia, GTFSRiderCategory, GTFSFareProduct, 
    GTFSTimeframe, GTFSFareLegRule, GTFSFareTransferRule
)

__all__ = [
    # Base models
    'Agency', 'FunctionalArea', 'Function', 'Vendor', 'Component',
    'IntegrationPoint', 'UserRole', 'UpdateLog', 'Standard', 'TagGroup', 'Tag',
    'User', 'VerifiedAgencyDomain',
    
    # GTFS models  
    'GTFSAgency', 'GTFSStop', 'GTFSRoute', 'GTFSCalendar', 'GTFSCalendarDate',
    'GTFSTrip', 'GTFSStopTime', 'GTFSShape', 'GTFSFeedInfo',
    'GTFSFareMedia', 'GTFSRiderCategory', 'GTFSFareProduct', 
    'GTFSTimeframe', 'GTFSFareLegRule', 'GTFSFareTransferRule'
]

