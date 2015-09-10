from ckan import model
from ckan.logic import NotFound, ValidationError
from ckan.lib.dictization import model_dictize
from ckanext.ytp.request.model import MemberRequest
from ckanext.ytp.request.helper import get_organization_admins
import logic
import logging
import ckan.new_authz as authz


log = logging.getLogger(__name__)

def member_requests_mylist(context, data_dict):
    ''' Users wil see a list of her member requests
    '''
    logic.check_access('member_requests_mylist', context, data_dict)

    user = context.get('user',None)
    if authz.is_sysadmin(user):
        raise ValidationError({}, {_("Role"): _("As a sysadmin, you already have access to all organizations")})
        
    user_object = model.User.get(user)
    #Return all pending or active memberships for all organizations for the user in context
    requests = model.Session.query(MemberRequest).filter(MemberRequest.member_id == user_object.id).all()
    return _member_request_list_dictize(requests,context)

def member_requests_list(context, data_dict):
    ''' Organization admins/editors will see a list of member requests to be approved.
    :param group: name of the group (optional)
    :type group: string
    '''
    logic.check_access('member_requests_list', context, data_dict)

    user = context.get('user',None)
    user_object = model.User.get(user)
    is_sysadmin = authz.is_sysadmin(user)

    query = model.Session.query(model.Member).filter(model.Member.table_name == "user").filter(model.Member.state == 'pending')

    if not is_sysadmin:
        admin_in_groups = model.Session.query(model.Member).filter(model.Member.state == "active").filter(model.Member.table_name == "user") \
            .filter(model.Member.capacity == 'admin').filter(model.Member.table_id == user_object.id)

        if admin_in_groups.count() <= 0:
            return []

        query = query.filter(model.Member.group_id.in_(admin_in_groups.values(model.Member.group_id)))

    group = data_dict.get('group', None)
    if group:
        group_object = model.Group.get(group)
        if group_object:
            query = query.filter(model.Member.group_id == group_object.id)

    members = query.all()

    return _member_list_dictize(members, context)

def member_request_show(context, data_dict):
    ''' Create new member request. User is taken from context.
    :param member: id of the member object
    :type member: string
    :param fetch_user: fetch related user data
    :type fetch_user: boolean
    '''
    logic.check_access('member_request_show', context, data_dict)

    model = context['model']
    member_id = data_dict.get("member")
    fetch_user = data_dict.get("fetch_user", False)
    member = model.Session.query(model.Member).get(member_id)

    if not member.group.is_organization:
        raise NotFound

    data = model_dictize.member_dictize(member, context)

    if fetch_user:
        member_user = model.Session.query(model.User).get(member.table_id)
        data['user'] = model_dictize.user_dictize(member_user, context)

    return data

@logic.side_effect_free
def get_available_roles(context, data_dict=None):    
    roles = logic.get_action("member_roles_list")(context,{})

    #Remove member role from the list
    roles = [role for role in roles if role['value'] != 'member']
    
    #If organization has no associated admin, then role editor is not available
    model = context['model']
    organization_id = logic.get_or_bust(data_dict, 'organization_id')

    if organization_id:
        if get_organization_admins(organization_id):
            roles = [role for role in roles if role['value'] != 'editor']
        return roles
    else:
        return None

def _member_request_list_dictize(obj_list, context, sort_key=lambda x: x['member_id'], reverse=False):
    """Helper to convert member requests list to dictionary """
    result_list = []
    for obj in obj_list:
        member_dict = {}
        user = model.Session.query(model.User).get(obj.member_id)
        organization = model.Session.query(model.Group).get(obj.organization_id)
        member_dict['member_name'] = user.name
        member_dict['organization_name'] = organization.name
        member_dict['state'] = obj.status
        member_dict['role'] = obj.role
        member_dict['request_date'] = obj.request_date.strftime("%d - %b - %Y");
        member_dict['handling_date'] = None
        if obj.handling_date:
            member_dict['handling_date'] = obj.handling_date.strftime("%d - %b - %Y");
        result_list.append(member_dict)
    return result_list
    #return sorted(result_list, key=sort_key, reverse=reverse)

def _member_list_dictize(obj_list, context, sort_key=lambda x: x['group_id'], reverse=False):
    """ Helper to convert member list to dictionary """
    result_list = []
    for obj in obj_list:
        member_dict = model_dictize.member_dictize(obj, context)
        member_dict['group_name'] = obj.group.name
        user = model.Session.query(model.User).get(obj.table_id)
        member_dict['user_name'] = user.name
        result_list.append(member_dict)
    return sorted(result_list, key=sort_key, reverse=reverse)

