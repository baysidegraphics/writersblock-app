"""Separate digital-output contract. No player, clickable choices or tracking exist."""
from abc import ABC,abstractmethod
from .state import get_data
from .validation import validate

SCHEMA_VERSION='wbs.educational-interactive.design.v1'


class DigitalInteractiveOutput(ABC):
    """Future adapters must implement a player and input/accessibility semantics."""
    implemented=False
    @abstractmethod
    def render_package(self,snapshot):
        raise NotImplementedError('No digital interactive player is implemented.')


class UnimplementedDigitalOutput(DigitalInteractiveOutput):
    def render_package(self,snapshot):
        raise NotImplementedError('Digital interaction is design-only; export a printable activity book instead.')


def interface_blueprint(snapshot):
    errors=validate(snapshot)
    if errors:raise ValueError('; '.join(errors))
    values=get_data(snapshot)
    return {'schema':SCHEMA_VERSION,'design_only':True,'implemented':False,
            'capabilities':{'clickable_choices':False,'learner_tracking':False,'digital_player':False},
            'age_band':values.get('age_band'),'subject_area':values.get('subject_area'),
            'units':values.get('units') or [],'choice_definitions':values.get('choices') or [],
            'activity_definitions':values.get('activities') or [],
            'future_interface':['render_unit(unit_number)','choose(choice_id, option_id)','submit_response(activity_id, response)','accessible_alternative(control_id)']}
