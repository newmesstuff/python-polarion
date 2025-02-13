import copy
import os
import requests
from zeep import xsd
from .base.comments import Comments
from .record import Record
from .factory import Creator


class Testrun(Comments):
    """
    Create a Polarion testrun object from uri or directly with Polarion content

    :param polarion: Polarion client object
    :param uri: Polarion uri
    :param polarion_test_run: The data from Polarion of this testrun

    :ivar records: An array of :class:`.Record`
    """

    def __init__(self, polarion, uri=None, polarion_test_run=None):
        super().__init__(polarion, None, None, uri)

        if uri is not None:
            service = self._polarion.getService('TestManagement')
            try:
                self._polarion_test_run = service.getTestRunByUri(uri)
            except Exception:
                raise Exception(f'Cannot find test run {uri}')

        elif polarion_test_run is not None:
            self._polarion_test_run = polarion_test_run
        else:
            raise Exception(f'Provide either an uri or polarion_test_run ')

        self._original_polarion_test_run = copy.deepcopy(self._polarion_test_run)
        self._buildWorkitemFromPolarion()

    def _buildWorkitemFromPolarion(self):
        if self._polarion_test_run is not None and not self._polarion_test_run.unresolvable:
            for attr, value in self._polarion_test_run.__dict__.items():
                for key in value:
                    if key == 'records':
                        setattr(self, '_' + key, value[key])
                    else:
                        setattr(self, key, value[key])

            self.records = []
            self._record_dict = {}
            if self._records is not None:
                # for r in self._records.TestRecord:
                for index, r in enumerate(self._records.TestRecord):
                    new_record = Record(self._polarion, self, r, index)
                    self.records.append(new_record)
                    if new_record.testcase_id not in self._record_dict:
                        self._record_dict[new_record.testcase_id] = [new_record]
                    else:
                        self._record_dict[new_record.testcase_id].append(new_record)

        else:
            raise Exception(f'Testrun not retrieved from Polarion')

    def _reloadFromPolarion(self):
        service = self._polarion.getService('TestManagement')
        self._polarion_test_run = service.getTestRunByUri(self.uri)
        self._buildWorkitemFromPolarion()
        self._original_polarion_test_run = copy.deepcopy(self._polarion_test_run)

    def hasTestCase(self, id):
        """
        Checks if the the specified test case id is in the records.

        :param id: The test case id
        :return: True/False
        :rtype: boolean
        """
        if id in self._record_dict:
            return True
        return False

    def getTestCase(self, id, iteration : int = 0):
        """
        Get the specified test case record from the test run records

        :param id: The test case id
        :param iteration: The test case iteration
        :return: Specified record if it exists
        :rtype: Record
        """
        if iteration < 0:
            raise Exception('Test case iteration must be positive.')
        if self.hasTestCase(id):
            return self._record_dict[id][iteration]
        return None

    def hasAttachment(self):
        """
        Checks if the test run has attachments

        :return: True/False
        :rtype: boolean
        """
        if self.attachments is not None:
            return True
        return False

    def getAttachment(self, file_name):
        """
        Get the attachment data

        :param file_name: The attachment file name
        :return: list of bytes
        :rtype: bytes[]
        """
        service = self._polarion.getService('TestManagement')
        at = service.getTestRunAttachment(self.uri, file_name)

        if at is not None:
            return self._polarion.downloadFromSvn(at.url)
        raise Exception(f'Could not download attachment {file_name}')

    def saveAttachmentAsFile(self, file_name, file_path):
        """
        Save an attachment to file.

        :param file_name: The attachment file name
        :param file_path: File where to save the attachment
        """
        bin = self.getAttachment(file_name)
        with open(file_path, "wb") as file:
            file.write(bin)

    def deleteAttachment(self, file_name):
        """
        Delete an attachment.

        :param file_name: The attachment file name
        """
        service = self._polarion.getService('TestManagement')
        service.deleteTestRunAttachment(self.uri, file_name)
        self._reloadFromPolarion()

    def addAttachment(self, file_path, title):
        """
        Upload an attachment

        :param file_path: Source file to upload
        :param title: The title of the attachment
        """
        service = self._polarion.getService('TestManagement')
        file_name = os.path.split(file_path)[1]
        with open(file_path, "rb") as file_content:
            service.addAttachmentToTestRun(self.uri, file_name, title, file_content.read())
        self._reloadFromPolarion()

    def addTestcase(self, workitem, test_parameters : list = []):
        """
        Add a workitem to the test run. A test case cannot be added to a template.
        :param workitem: Workitem object
        :param test_parameters: List of parameter objects
        """
        service = self._polarion.getService('TestManagement')

        # Convert provided test parameters list
        test_parameters_dict = dict([(test_parameter['name'], test_parameter['value']) for test_parameter in test_parameters])
        
        # Get test parameter of test case
        test_case_parameter_names = service.getTestCaseParameterNames(workitem.uri)

        # Add test parameters to test record if they are part of the test case
        test_parameters_list = []
        for test_case_parameter_name in test_case_parameter_names:
            if test_case_parameter_name in test_parameters_dict.keys():
                test_parameters_list.append(self._polarion.ParameterType(test_case_parameter_name, test_parameters_dict['test_case_parameter_name']))
            else:
                test_parameters_list.append(self._polarion.ParameterType(test_case_parameter_name, 'not specified'))

        # Add URI and if availabe revision to test record
        testCaseUriAndRevision = workitem.uri.split('%')
        if len(testCaseUriAndRevision) > 1:
            new_record = self._polarion.TestRecordType(testCaseURI=testCaseUriAndRevision[0], testCaseRevision=testCaseUriAndRevision[1], testParameters=test_parameters_list)
        else:            
            new_record = self._polarion.TestRecordType(testCaseURI=testCaseUriAndRevision[0], testParameters=test_parameters_list)

        # Add test record to test run and reload item
        service.addTestRecordToTestRun(self.uri, new_record)
        self._reloadFromPolarion()

    def updateAttachment(self, file_path, title):
        """
        Upload an attachment

        :param file_path: Source file to upload
        :param title: The title of the attachment
        """
        service = self._polarion.getService('TestManagement')
        file_name = os.path.split(file_path)[1]
        with open(file_path, "rb") as file_content:
            service.updateTestRunAttachment(self.uri, file_name, title, file_content.read())
        self._reloadFromPolarion()

    def save(self):
        """
        Update the testrun in polarion
        """
        updated_item = {}
        skip = ['records']

        for attr, value in self._polarion_test_run.__dict__.items():
            for key in value:
                if key in skip:
                    continue
                current_value = getattr(self, key)
                prev_value = getattr(self._original_polarion_test_run, key)
                if current_value != prev_value:
                    updated_item[key] = current_value
        if len(updated_item) > 0:
            updated_item['uri'] = self.uri
            service = self._polarion.getService('TestManagement')
            service.updateTestRun(updated_item)
            self._reloadFromPolarion()

    def __repr__(self):
        return f'Testrun {self.id} ({self.title}) created {self.created}'

    def __str__(self):
        return f'Testrun {self.id} ({self.title}) created {self.created}'


class TestrunCreator(Creator):
    def createFromUri(self, polarion, project, uri):
        return Testrun(polarion, uri)
