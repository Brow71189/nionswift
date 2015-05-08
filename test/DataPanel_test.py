# standard libraries
import contextlib
import logging
import unittest

# third party libraries
import numpy

# local libraries
from nion.swift import Application
from nion.swift import DataPanel
from nion.swift import DocumentController
from nion.swift import DisplayPanel
from nion.swift.model import DataGroup
from nion.swift.model import DataItem
from nion.swift.model import DataItemsBinding
from nion.swift.model import DocumentModel
from nion.swift.model import Operation
from nion.ui import Test


class TestDataPanelClass(unittest.TestCase):

    def setUp(self):
        self.app = Application.Application(Test.UserInterface(), set_global=False)

    def tearDown(self):
        pass

    # make sure we can delete top level items, and child items
    def test_image_panel_delete(self):
        document_model = DocumentModel.DocumentModel()
        document_controller = DocumentController.DocumentController(self.app.ui, document_model, workspace_id="library")
        # data_group
        #   data_item1
        #     data_item1a
        #   data_item2
        #     data_item2a
        #   data_item3
        data_group = DataGroup.DataGroup()
        data_group.title = "data_group"
        document_model.append_data_group(data_group)
        data_item1 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item1.title = "data_item1"
        document_model.append_data_item(data_item1)
        data_group.append_data_item(data_item1)
        data_item1a = DataItem.DataItem()
        data_item1a.title = "data_item1a"
        operation1a = Operation.OperationItem("invert-operation")
        operation1a.add_data_source(data_item1._create_test_data_source())
        data_item1a.set_operation(operation1a)
        document_model.append_data_item(data_item1a)
        data_group.append_data_item(data_item1a)
        data_item2 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item2.title = "data_item2"
        document_model.append_data_item(data_item2)
        data_group.append_data_item(data_item2)
        data_item2a = DataItem.DataItem()
        data_item2a.title = "data_item2a"
        operation2a = Operation.OperationItem("invert-operation")
        operation2a.add_data_source(data_item2._create_test_data_source())
        data_item2a.set_operation(operation2a)
        document_model.append_data_item(data_item2a)
        data_group.append_data_item(data_item2a)
        data_item3 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item3.title = "data_item3"
        document_model.append_data_item(data_item3)
        data_group.append_data_item(data_item3)
        display_panel = DisplayPanel.DisplayPanel(document_controller, dict())
        display_panel.set_displayed_data_item(data_item1)
        data_panel = document_controller.find_dock_widget("data-panel").panel
        document_controller.data_browser_controller.set_data_browser_selection(data_item=data_item1)
        document_controller.periodic()
        document_controller.selected_display_panel = display_panel
        # first delete a child of a data item
        self.assertEqual(len(document_model.get_dependent_data_items(data_item1)), 1)
        self.assertEqual(len(data_group.data_items), 5)
        document_controller.data_browser_controller.set_data_browser_selection(data_item=data_item1a)
        data_panel.data_list_controller._delete_pressed([3])
        self.assertEqual(len(document_model.get_dependent_data_items(data_item1)), 0)
        # now delete a child of a data group
        self.assertEqual(len(data_group.data_items), 4)
        data_panel.data_list_controller.list_widget.on_selection_changed([2])
        data_panel.data_list_controller._delete_pressed([2])
        self.assertEqual(len(data_group.data_items), 2)
        display_panel.canvas_item.close()
        display_panel.close()
        document_controller.close()

    # make sure switching between two views containing data items from the same group
    # switch between those data items in the data panel when switching.
    def test_selected_data_item_persistence(self):
        library_storage = DocumentModel.FilePersistentStorage()
        document_model = DocumentModel.DocumentModel(library_storage=library_storage)
        parent_data_group = DataGroup.DataGroup()
        parent_data_group.title = "parent_data_group"
        data_group = DataGroup.DataGroup()
        data_group.title = "data_group"
        parent_data_group.append_data_group(data_group)
        document_model.append_data_group(parent_data_group)
        data_item1 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item1.title = "data_item1"
        document_model.append_data_item(data_item1)
        data_group.append_data_item(data_item1)
        data_item2 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item2.title = "data_item2"
        document_model.append_data_item(data_item2)
        data_group.append_data_item(data_item2)
        document_controller = DocumentController.DocumentController(self.app.ui, document_model, workspace_id="library")
        data_panel = document_controller.find_dock_widget("data-panel").panel
        self.assertEqual(data_panel.data_group_widget.parent_id, 0)
        self.assertEqual(data_panel.data_group_widget.parent_row, -1)
        self.assertEqual(data_panel.data_group_widget.index, -1)
        self.assertEqual(data_panel.data_list_controller.list_widget.current_index, -1)
        document_controller.data_browser_controller.set_data_browser_selection(data_group=data_group, data_item=data_item1)
        self.assertEqual(data_panel.data_group_widget.parent_id, 1)
        self.assertEqual(data_panel.data_group_widget.parent_row, 0)
        self.assertEqual(data_panel.data_group_widget.index, 0)
        self.assertEqual(data_panel.data_list_controller.list_widget.current_index, 0)
        document_controller.data_browser_controller.set_data_browser_selection(data_group=data_group, data_item=data_item2)
        self.assertEqual(data_panel.data_group_widget.parent_id, 1)
        self.assertEqual(data_panel.data_group_widget.parent_row, 0)
        self.assertEqual(data_panel.data_group_widget.index, 0)
        self.assertEqual(data_panel.data_list_controller.list_widget.current_index, 1)
        document_controller.data_browser_controller.set_data_browser_selection(data_group=data_group, data_item=data_item1)
        self.assertEqual(data_panel.data_group_widget.parent_id, 1)
        self.assertEqual(data_panel.data_group_widget.parent_row, 0)
        self.assertEqual(data_panel.data_group_widget.index, 0)
        self.assertEqual(data_panel.data_list_controller.list_widget.current_index, 0)

    # make sure switching between two data items in different groups works
    # then make sure the same group is selected if the data item is in multiple groups
    def test_selected_group_persistence(self):
        document_model = DocumentModel.DocumentModel()
        # create data_item2 earlier than data_item1 so they sort to match old test setup
        data_item2 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item2.title = "Data 2"
        data_item1 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item1.title = "Data 1"
        parent_data_group = DataGroup.DataGroup()
        parent_data_group.title = "parent_data_group"
        data_group1 = DataGroup.DataGroup()
        data_group1.title = "Group 1"
        parent_data_group.append_data_group(data_group1)
        document_model.append_data_item(data_item1)
        data_group1.append_data_item(data_item1)
        data_group2 = DataGroup.DataGroup()
        data_group2.title = "Group 2"
        parent_data_group.append_data_group(data_group2)
        document_model.append_data_item(data_item2)
        data_group2.append_data_item(data_item2)
        document_model.append_data_group(parent_data_group)
        document_controller = DocumentController.DocumentController(self.app.ui, document_model, workspace_id="library")
        data_panel = document_controller.find_dock_widget("data-panel").panel
        data_panel.focused = True
        self.assertEqual(data_panel.data_group_widget.parent_id, 0)
        self.assertEqual(data_panel.data_group_widget.parent_row, -1)
        self.assertEqual(data_panel.data_group_widget.index, -1)
        self.assertEqual(data_panel.data_list_controller.list_widget.current_index, -1)
        document_controller.data_browser_controller.set_data_browser_selection(data_group=data_group1, data_item=data_item1)
        self.assertEqual(data_panel.data_group_widget.parent_id, 1)
        self.assertEqual(data_panel.data_group_widget.parent_row, 0)
        self.assertEqual(data_panel.data_group_widget.index, 0)
        self.assertEqual(data_panel.data_list_controller.list_widget.current_index, 0)
        document_controller.data_browser_controller.set_data_browser_selection(data_group=data_group2, data_item=data_item2)
        self.assertEqual(data_panel.data_group_widget.parent_id, 1)
        self.assertEqual(data_panel.data_group_widget.parent_row, 0)
        self.assertEqual(data_panel.data_group_widget.index, 1)
        self.assertEqual(data_panel.data_list_controller.list_widget.current_index, 0)
        document_controller.data_browser_controller.set_data_browser_selection(data_group=data_group1, data_item=data_item1)
        self.assertEqual(data_panel.data_group_widget.parent_id, 1)
        self.assertEqual(data_panel.data_group_widget.parent_row, 0)
        self.assertEqual(data_panel.data_group_widget.index, 0)
        self.assertEqual(data_panel.data_list_controller.list_widget.current_index, 0)
        # now make sure if a data item is in multiple groups, the right one is selected
        data_group2.append_data_item(data_item1)
        document_controller.data_browser_controller.set_data_browser_selection(data_group=data_group2, data_item=data_item2)
        data_panel.data_list_controller.list_widget.on_selection_changed([1])  # data_group2 now has data_item1 selected
        document_controller.data_browser_controller.set_data_browser_selection(data_group=data_group1, data_item=data_item1)
        data_panel.data_list_controller.list_widget.on_selection_changed([0])  # data_group1 still has data_item1 selected
        self.assertEqual(document_controller.data_browser_controller.data_item, data_item1)
        self.assertEqual(data_panel.data_group_widget.parent_id, 1)
        self.assertEqual(data_panel.data_group_widget.parent_row, 0)
        self.assertEqual(data_panel.data_group_widget.index, 0)
        self.assertEqual(data_panel.data_list_controller.list_widget.current_index, 0)
        document_controller.data_browser_controller.set_data_browser_selection(data_group=data_group2, data_item=data_item1)
        self.assertEqual(data_panel.data_group_widget.parent_id, 1)
        self.assertEqual(data_panel.data_group_widget.parent_row, 0)
        self.assertEqual(data_panel.data_group_widget.index, 1)
        self.assertEqual(data_panel.data_list_controller.list_widget.current_index, 1)
        document_controller.data_browser_controller.set_data_browser_selection(data_group=data_group1, data_item=data_item1)
        self.assertEqual(document_controller.data_browser_controller.data_item, data_item1)
        self.assertEqual(data_panel.data_group_widget.parent_id, 1)
        self.assertEqual(data_panel.data_group_widget.parent_row, 0)
        self.assertEqual(data_panel.data_group_widget.index, 0)
        self.assertEqual(data_panel.data_list_controller.list_widget.current_index, 0)
        # now make sure group selections are preserved
        document_controller.data_browser_controller.set_data_browser_selection(data_group=data_group1, data_item=data_item1)
        data_panel.data_group_widget.on_selection_changed(((1, 0, 1), ))  # data_group1 now has data_group2 selected
        data_panel.data_list_controller.list_widget.on_selection_changed([])  # data_group1 now has no data item selected
        self.assertIsNone(document_controller.data_browser_controller.data_item)
        self.assertEqual(data_panel.data_group_widget.parent_id, 1)
        self.assertEqual(data_panel.data_group_widget.parent_row, 0)
        self.assertEqual(data_panel.data_group_widget.index, 1)
        self.assertEqual(data_panel.data_list_controller.list_widget.current_index, -1)
        document_controller.data_browser_controller.set_data_browser_selection(data_group=data_group2, data_item=data_item1)
        self.assertEqual(data_panel.data_group_widget.parent_id, 1)
        self.assertEqual(data_panel.data_group_widget.parent_row, 0)
        self.assertEqual(data_panel.data_group_widget.index, 1)
        self.assertEqual(data_panel.data_list_controller.list_widget.current_index, 1)
        document_controller.data_browser_controller.set_data_browser_selection(data_group=data_group2)
        self.assertIsNone(document_controller.data_browser_controller.data_item)
        self.assertEqual(data_panel.data_group_widget.parent_id, 1)
        self.assertEqual(data_panel.data_group_widget.parent_row, 0)
        self.assertEqual(data_panel.data_group_widget.index, 1)
        self.assertEqual(data_panel.data_list_controller.list_widget.current_index, -1)
        # make sure root level is handled ok
        document_controller.data_browser_controller.set_data_browser_selection(data_group=data_group2)
        data_panel.data_group_widget.on_selection_changed(((0, -1, 0), ))
        document_controller.data_browser_controller.set_data_browser_selection(data_group=data_group2, data_item=data_item1)
        self.assertEqual(data_panel.data_group_widget.parent_id, 1)
        self.assertEqual(data_panel.data_group_widget.parent_row, 0)
        self.assertEqual(data_panel.data_group_widget.index, 1)
        self.assertEqual(data_panel.data_list_controller.list_widget.current_index, 1)

    def test_selection_during_operations(self):
        document_model = DocumentModel.DocumentModel()
        document_controller = DocumentController.DocumentController(self.app.ui, document_model, workspace_id="library")
        # data_item1
        #   inverted
        # data_item2
        data_item1 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item1.title = "data_item1"
        document_model.append_data_item(data_item1)
        data_item2 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item2.title = "data_item2"
        document_model.append_data_item(data_item2)
        # finished setting up
        data_panel = document_controller.find_dock_widget("data-panel").panel
        data_panel.focused = True
        document_controller.data_browser_controller.set_data_browser_selection(data_item=data_item1)
        # make sure our preconditions are right
        self.assertEqual(document_controller.selected_display_specifier.data_item, data_item1)
        self.assertEqual(len(document_model.get_dependent_data_items(data_item1)), 0)
        # add processing and make sure it appeared
        self.assertEqual(document_controller.data_browser_controller.data_item, data_item1)
        inverted_data_item = document_controller.processing_invert().data_item
        self.assertEqual(len(document_model.get_dependent_data_items(data_item1)), 1)
        # now make sure data panel shows it as selected
        self.assertEqual(document_controller.data_browser_controller.data_item, inverted_data_item)
        # switch away and back and make sure selection is still correct
        document_controller.data_browser_controller.set_data_browser_selection(data_item=data_item2)
        document_controller.data_browser_controller.set_data_browser_selection(data_item=inverted_data_item)
        self.assertEqual(document_controller.data_browser_controller.data_item, inverted_data_item)
        document_controller.close()

    def test_existing_item_gets_initially_added_to_binding_data_items(self):
        document_model = DocumentModel.DocumentModel()
        document_controller = DocumentController.DocumentController(self.app.ui, document_model, workspace_id="library")
        data_group = DataGroup.DataGroup()
        data_group.title = "data_group"
        document_controller.document_model.append_data_group(data_group)
        data_item1 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item1.title = "data_item1"
        document_model.append_data_item(data_item1)
        data_group.append_data_item(data_item1)
        data_item2 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item2.title = "data_item2"
        document_model.append_data_item(data_item2)
        data_group.append_data_item(data_item2)
        binding = DataItemsBinding.DataItemsInContainerBinding()
        binding.container = data_group
        self.assertTrue(data_item1 in binding.data_items)
        data_panel = document_controller.find_dock_widget("data-panel").panel
        document_controller.data_browser_controller.set_data_browser_selection(data_group=data_group, data_item=data_item1)
        binding.close()
        binding = None

    def test_data_group_data_items_binding_should_close_nicely(self):
        document_model = DocumentModel.DocumentModel()
        document_controller = DocumentController.DocumentController(self.app.ui, document_model, workspace_id="library")
        data_group = DataGroup.DataGroup()
        data_group.title = "data_group"
        document_controller.document_model.append_data_group(data_group)
        data_item1 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item1.title = "data_item1"
        document_model.append_data_item(data_item1)
        data_group.append_data_item(data_item1)
        data_item2 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item2.title = "data_item2"
        document_model.append_data_item(data_item2)
        data_group.append_data_item(data_item2)
        binding = DataItemsBinding.DataItemsInContainerBinding()
        binding.container = data_group
        self.assertTrue(data_item1 in binding.data_items)
        binding.close()
        binding = None

    def test_data_group_data_items_binding_should_replace_data_group_with_itself_without_failing(self):
        document_model = DocumentModel.DocumentModel()
        document_controller = DocumentController.DocumentController(self.app.ui, document_model, workspace_id="library")
        data_group = DataGroup.DataGroup()
        data_group.title = "data_group"
        document_controller.document_model.append_data_group(data_group)
        data_item1 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item1.title = "data_item1"
        document_model.append_data_item(data_item1)
        data_group.append_data_item(data_item1)
        data_item2 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item2.title = "data_item2"
        document_model.append_data_item(data_item2)
        data_group.append_data_item(data_item2)
        binding = DataItemsBinding.DataItemsInContainerBinding()
        binding.container = data_group
        binding.container = data_group
        self.assertTrue(data_item1 in binding.data_items)
        binding.close()
        binding = None

    def test_add_remove_sync(self):
        document_model = DocumentModel.DocumentModel()
        document_controller = DocumentController.DocumentController(self.app.ui, document_model, workspace_id="library")
        data_group = DataGroup.DataGroup()
        data_group.title = "data_group"
        document_controller.document_model.append_data_group(data_group)
        data_item1 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item1.title = "data_item1"
        data_group.append_data_item(data_item1)
        document_model.append_data_item(data_item1)
        data_item2 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item2.title = "data_item2"
        data_group.append_data_item(data_item2)
        document_model.append_data_item(data_item2)
        data_item3 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item3.title = "data_item3"
        document_model.append_data_item(data_item3)
        data_group.append_data_item(data_item3)
        data_panel = document_controller.find_dock_widget("data-panel").panel
        document_controller.data_browser_controller.set_data_browser_selection(data_group=data_group, data_item=data_item2)
        document_controller.periodic()
        data_panel.periodic()
        # verify assumptions
        self.assertEqual(data_panel.data_list_controller._get_model_data_count(), 3)
        # delete 2nd item
        data_group.remove_data_item(data_group.data_items[1])
        document_controller.periodic()
        data_panel.periodic()
        self.assertEqual(data_panel.data_list_controller._get_model_data_count(), 2)
        self.assertEqual(data_panel.data_list_controller._get_model_data(0)["display"], str(data_item1.title))
        self.assertEqual(data_panel.data_list_controller._get_model_data(1)["display"], str(data_item3.title))
        # insert new item
        data_item4 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item4.title = "data_item4"
        data_group.insert_data_item(1, data_item4)
        document_controller.periodic()
        data_panel.periodic()
        self.assertEqual(data_panel.data_list_controller._get_model_data_count(), 3)
        self.assertEqual(data_panel.data_list_controller._get_model_data(0)["display"], str(data_item1.title))
        self.assertEqual(data_panel.data_list_controller._get_model_data(1)["display"], str(data_item4.title))
        self.assertEqual(data_panel.data_list_controller._get_model_data(2)["display"], str(data_item3.title))

    def test_select_after_receive_files(self):
        document_model = DocumentModel.DocumentModel()
        document_controller = DocumentController.DocumentController(self.app.ui, document_model, workspace_id="library")
        data_item = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item.title = "data_item"
        data_group = DataGroup.DataGroup()
        document_controller.document_model.append_data_group(data_group)
        document_model.append_data_item(data_item)
        data_group.append_data_item(data_item)
        data_panel = document_controller.find_dock_widget("data-panel").panel
        data_panel.focused = True
        self.assertIsNone(document_controller.data_browser_controller.data_item)
        data_panel.data_group_model_receive_files([":/app/scroll_gem.png"], data_group, index=0, threaded=False)
        self.assertEqual(document_controller.data_browser_controller.data_item, data_group.data_items[0])

    def test_data_panel_remove_group(self):
        document_model = DocumentModel.DocumentModel()
        document_controller = DocumentController.DocumentController(self.app.ui, document_model, workspace_id="library")
        data_group1 = DataGroup.DataGroup()
        data_group1.title = "data_group1"
        data_item1 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item1.title = "Green 1"
        document_model.append_data_item(data_item1)
        data_group1.append_data_item(data_item1)
        document_controller.document_model.append_data_group(data_group1)
        green_group = DataGroup.DataGroup()
        green_group.title = "green_group"
        green_group.append_data_item(data_item1)
        document_controller.document_model.insert_data_group(0, green_group)
        self.assertEqual(len(green_group.data_items), 1)
        data_panel = document_controller.find_dock_widget("data-panel").panel
        document_controller.remove_data_group_from_container(document_controller.document_model.data_groups[0], document_controller.document_model)
        document_controller.close()

    def test_data_panel_remove_item_by_key(self):
        document_model = DocumentModel.DocumentModel()
        document_controller = DocumentController.DocumentController(self.app.ui, document_model, workspace_id="library")
        data_group1 = DataGroup.DataGroup()
        data_group1.title = "data_group1"
        data_item1 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item1.title = "Green 1"
        document_model.append_data_item(data_item1)
        data_group1.append_data_item(data_item1)
        green_group = DataGroup.DataGroup()
        green_group.title = "green_group"
        green_group.append_data_item(data_item1)
        document_controller.document_model.insert_data_group(0, green_group)
        document_controller.document_model.append_data_group(data_group1)
        data_panel = document_controller.find_dock_widget("data-panel").panel
        document_controller.data_browser_controller.set_data_browser_selection(data_group=data_group1, data_item=data_item1)
        self.assertTrue(data_item1 in data_group1.data_items)
        data_panel.data_list_controller._delete_pressed([0])
        self.assertFalse(data_item1 in data_group1.data_items)
        document_controller.close()

    def test_remove_item_should_remove_children_when_both_parent_and_child_are_selected(self):
        document_model = DocumentModel.DocumentModel()
        document_controller = DocumentController.DocumentController(self.app.ui, document_model, workspace_id="library")
        data_item1 = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        data_item1.title = "data_item1"
        document_model.append_data_item(data_item1)
        data_item1a = DataItem.DataItem()
        data_item1a.title = "data_item1a"
        document_model.append_data_item(data_item1a)
        data_panel = document_controller.find_dock_widget("data-panel").panel
        document_controller.periodic()
        data_panel.data_list_controller._delete_pressed([0, 1])

    def test_data_panel_should_save_and_restore_state_when_no_data_group_is_selected(self):
        # TODO: implement data panel save/restore test
        self.assertTrue(True)

    def test_data_items_are_inserted_correctly_when_switching_from_none_to_all_selected(self):
        document_model = DocumentModel.DocumentModel()
        document_controller = DocumentController.DocumentController(self.app.ui, document_model, workspace_id="library")
        for i in xrange(3):
            data_item = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
            document_model.append_data_item(data_item)
        data_panel = document_controller.find_dock_widget("data-panel").panel
        data_panel.library_widget.on_selection_changed([(1, -1, 0)])
        data_panel.library_widget.on_selection_changed([(0, -1, 0)])

    def test_display_filter_filters_data(self):
        document_model = DocumentModel.DocumentModel()
        document_controller = DocumentController.DocumentController(self.app.ui, document_model, workspace_id="library")
        for i in xrange(3):
            data_item = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
            data_item.title = "X" if i != 1 else "Y"
            document_model.append_data_item(data_item)
        data_panel = document_controller.find_dock_widget("data-panel").panel
        document_controller.periodic()  # changes to filter will be queued. update that here.
        self.assertEqual(len(document_controller.filtered_data_items_binding.data_items), 3)
        document_controller.display_filter = lambda data_item: data_item.title == "Y"
        document_controller.periodic()  # changes to filter will be queued. update that here.
        self.assertEqual(len(document_controller.filtered_data_items_binding.data_items), 1)

    def test_changing_display_limits_causes_display_changed_message(self):
        # necessary to make the thumbnails update in the data panel
        data_item = DataItem.DataItem(numpy.zeros((256, 256), numpy.uint32))
        display_specifier = DataItem.DisplaySpecifier.from_data_item(data_item)
        display_changed_ref = [False]
        def display_changed():
            display_changed_ref[0] = True
        with contextlib.closing(display_specifier.display.display_changed_event.listen(display_changed)):
            display_specifier.display.display_limits = (0.25, 0.75)
            self.assertTrue(display_changed_ref[0])


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
