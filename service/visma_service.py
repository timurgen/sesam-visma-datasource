import json
import xmltodict
import requests
import os
import logging
from flask import Flask, Response, abort

APP = Flask(__name__)
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
# default values point to visma test api server
SERVICE_URL = os.environ.get("SERVICE_URL", "http://erp.vitari.no/vbws/")
CLIENT_ID = os.environ.get('CLIENT_ID', 9999)
GUID = os.environ.get('GUID', 'XXXX-XXXX-XXXX-XXXX-XXXX')

STATUS_STR = 'Status'
MESSAGE_STR = 'Message'

"""credentials are part of every request so we want to have it encrypted"""
if not SERVICE_URL.startswith("https://"):
    logging.error("CONNECTION NOT ENCRYPTED")
    # abort

logging.basicConfig(level=LOG_LEVEL)


def build_header(client_id, guid):
    """
    builds header part of request with given client id and API guid
    :param client_id: API client id
    :param guid: API client token/guid
    :return: XML string, header snippet to be inserted into xml request
    """
    return "<Header><ClientId>{}</ClientId><Guid>{}</Guid></Header>".format(client_id, guid)


def build_url(base_url, endpoint):
    """
    builds url for Get{endpoint}s query
    :param base_url: base service url
    :param endpoint: endpoint to query
    :return: String with query URL
    """
    if base_url is None or endpoint is None:
        raise ValueError("Invalid argument")
    return "{}{}.svc/Get{}s".format(base_url, endpoint, endpoint)


def resolve_id_property(entity_name):
    """Return string that intended to be used as id for given entity type"""
    data = {
        'Customer': 'CustomerNo',
        'Article': 'ProductNo',
        'Order': 'OrderNo',
        'Employee': 'EmployeeNo'
    }
    return data.get(entity_name, None)


def resolve_since_property(entity_name):
    """Return string that intended to be used as _updated for given entity type"""
    data = {
        'Customer': None,
        'Article': None,
        'Order': None,
        'Employee': None
    }
    return data.get(entity_name, None)


def get_filter(entity_name):
    data = {
        'Customer': '<Filters><CustomerNo Value1="0" Compare="GreaterThanOrEqualTo"/></Filters>'
    }
    return data.get(entity_name, None)


def get_payload(entity_name):
    data = {
        'Customer': '<?xml version="1.0" encoding="UTF-8"?><Customerinfo>{}<Status><MessageId/><Message/><MessageDetail/></Status>{}<Customer><AssociateNo/><CustomerNo/><InvoiceCustomerNo/><SendToAssociateNo/><Name/><ShortName/><Mobile/><Phone/><Fax/><EmailAddress/><WebPage/><CompanyNo/><CountryCode/><LanguageCode/><BankAccountNo/><PaymentTerms/><AddressLine1/><AddressLine2/><AddressLine3/><AddressLine4/><PostCode/><PostalArea/><VisitPostCode/><VisitPostalArea/><OrgUnit1>2</OrgUnit1><OrgUnit2/><OrgUnit3/><OrgUnit4/><OrgUnit5/><OrgUnit6/><OrgUnit7/><OrgUnit8/><OrgUnit9/><OrgUnit10/><OrgUnit11/><OrgUnit12/><Group1/><Group2/><Group3/><Group4/><Group5/><Group6/><Group7/><Group8/><Group9/><Group10/><Group11/><Group12/><CustomerPriceGroup1/><CustomerPriceGroup2/><CustomerPriceGroup3/><Information1/><Information2/><Information3/><Information4/><Information5/><Information6/><Information7/><Information8/></Customer></Customerinfo>',
        'Article': None,
        'Order': None,
        'Employee': None
    }
    return data.get(entity_name, None)


def fetch_and_process(url, entity_name):
    """
    Fetch/process and return data from Visma endpoint
    :param url:
    :param entity_name:
    :return: processed payload
    """
    logging.debug("Request url: %s", url)
    payload = get_payload(entity_name).format(build_header(CLIENT_ID, GUID),
                                              get_filter(entity_name))
    req = requests.post(url, payload)
    res = req.text
    res_dict = xmltodict.parse(res);

    root_element = '{}info'.format(entity_name)

    if root_element not in res_dict:
        abort(Response("Expected root element were not found in API response"))

    if STATUS_STR not in res_dict[root_element]:
        abort(Response("Status header were not found in API response"))

    status = res_dict[root_element][STATUS_STR]

    if MESSAGE_STR not in status or 'OK' != status[MESSAGE_STR]:
        abort(Response("Invalid response status: {} {}"
                       , status.get(MESSAGE_STR, 'not found'), status.get('MessageDetail', '')))

    if entity_name not in res_dict[root_element]:
        abort(Response("Payload were not found in API response"))

    response_payload = res_dict[root_element][entity_name]

    # resolve id
    id_property = resolve_id_property(entity_name)
    if id_property is not None:
        for item in response_payload:
            item['_id'] = item[id_property]

    return json.dumps(response_payload)


@APP.route('/datasets/<string:entity_name>/entities')
def get_entities(entity_name):
    """
    service entry point
    :param entity_name: which Visma endpoint  need to be queried
    :return: json response
    """
    endpoint_url = build_url(SERVICE_URL, entity_name)
    data = fetch_and_process(endpoint_url, entity_name)
    return Response(data, mimetype='application/json')


if __name__ == '__main__':
    logging.info("Starting service")
    APP.run(debug=True, host='0.0.0.0', threaded=True, port=os.environ.get('PORT', 5000))
