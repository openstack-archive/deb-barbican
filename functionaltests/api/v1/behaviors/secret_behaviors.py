"""
Copyright 2014-2015 Rackspace

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from functionaltests.api.v1.behaviors import base_behaviors
from functionaltests.api.v1.models import secret_models


class SecretBehaviors(base_behaviors.BaseBehaviors):

    def create_secret(self, model, headers=None):
        """Create a secret from the data in the model.

        :param model: The metadata used to create the secret
        :return: A tuple containing the response from the create
        and the href to the newly created secret
        """

        resp = self.client.post('secrets', request_model=model,
                                extra_headers=headers)

        returned_data = self.get_json(resp)
        secret_ref = returned_data.get('secret_ref')
        if secret_ref:
            self.created_entities.append(secret_ref)
        return resp, secret_ref

    def update_secret_payload(self, secret_ref, payload, payload_content_type,
                              payload_content_encoding=None):
        """Updates a secret's payload data.

        :param secret_ref: HATEOS ref of the secret to be updated
        :param payload: new payload to be sent to server
        :param payload_content_type: value for the Content-Type header
        :param payload_content_encoding: value for the Content-Encoding header
        :return: the response from the PUT update
        """

        if payload_content_encoding is None:
            headers = {'Content-Type': payload_content_type}
        else:
            headers = {'Content-Type': payload_content_type,
                       'Content-Encoding': payload_content_encoding}

        return self.client.put(secret_ref, data=payload, extra_headers=headers)

    def get_secret(self, secret_ref, payload_content_type,
                   payload_content_encoding=None):

        headers = {'Accept': payload_content_type,
                   'Accept-Encoding': payload_content_encoding}

        return self.client.get(secret_ref + '/payload',
                               extra_headers=headers)

    def get_secret_based_on_content_type(self, secret_ref,
                                         payload_content_type,
                                         payload_content_encoding=None):
        """Retrieves a secret's payload based on the content type

        NOTE: This way will be deprecated in subsequent versions of the API.
        """

        headers = {'Accept': payload_content_type,
                   'Accept-Encoding': payload_content_encoding}

        return self.client.get(secret_ref, extra_headers=headers)

    def get_secret_metadata(self, secret_ref):
        """Retrieves a secret's metadata.

        :param secret_ref: HATEOS ref of the secret to be retrieved
        :return: A request response object
        """
        return self.client.get(
            secret_ref, response_model_type=secret_models.SecretModel)

    def get_secrets(self, limit=10, offset=0, name_filter=None,
                    extra_headers=None):
        """Handles getting a list of secrets.

        :param limit: limits number of returned secrets
        :param offset: represents how many records to skip before retrieving
                       the list
        :param name_filter: optional filter to limit the returned secrets to
                        those whose name matches the filter.
        :param extra_headers: Optional HTTP headers to add to the request
        """
        params = {'limit': limit, 'offset': offset}
        if name_filter:
            params['name'] = name_filter
        resp = self.client.get('secrets', params=params,
                               extra_headers=extra_headers)

        secrets_list = self.get_json(resp)

        secrets, next_ref, prev_ref = self.client.get_list_of_models(
            secrets_list, secret_models.SecretModel)

        return resp, secrets, next_ref, prev_ref

    def delete_secret(self, secret_ref, extra_headers=None,
                      expected_fail=False):
        """Delete a secret.

        :param secret_ref: HATEOS ref of the secret to be deleted
        :param extra_headers: Optional HTTP headers to add to the request
        :param expected_fail: If test is expected to fail the deletion
        :return A request response object
        """
        resp = self.client.delete(secret_ref, extra_headers=extra_headers)

        if not expected_fail:
            self.created_entities.remove(secret_ref)

        return resp

    def delete_all_created_secrets(self):
        """Delete all of the secrets that we have created."""
        slist = []

        for entity in self.created_entities:
            slist.append(entity)

        for secret_ref in slist:
            self.delete_secret(secret_ref)
