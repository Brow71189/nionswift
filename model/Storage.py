# standard libraries
import copy
import functools
import logging
import os
import pickle
import queue
import sqlite3
import sys
import threading
import time
import uuid
import weakref

# third party libraries
# None

# local libraries
from nion.ui import Observable


class SuspendableCache(object):

    def __init__(self, storage_cache):
        self.__storage_cache = storage_cache
        self.__cache = dict()
        self.__cache_remove = dict()
        self.__cache_dirty = dict()
        self.__cache_mutex = threading.RLock()
        self.__cache_delayed = False

    # the cache system stores values that are expensive to calculate for quick retrieval.
    # an item can be marked dirty in the cache so that callers can determine whether that
    # value needs to be recalculated. marking a value as dirty doesn't affect the current
    # value in the cache. callers can still retrieve the latest value for an item in the
    # cache even when it is marked dirty. this way the cache is used to retrieve the best
    # available data without doing additional calculations.

    def suspend_cache(self):
        with self.__cache_mutex:
            self.__cache_delayed = True

    # move local cache items into permanent cache when transaction is finished.
    def spill_cache(self):
        with self.__cache_mutex:
            cache_copy = copy.copy(self.__cache)
            cache_dirty_copy = copy.copy(self.__cache_dirty)
            cache_remove_copy = copy.copy(self.__cache_remove)
            self.__cache.clear()
            self.__cache_remove.clear()
            self.__cache_dirty.clear()
            self.__cache_delayed = False
        if self.__storage_cache:
            for object_id, (object, object_dict) in iter(cache_copy.items()):
                _, object_dirty_dict = cache_dirty_copy.get(id(object), (object, dict()))
                for key, value in iter(object_dict.items()):
                    dirty = object_dirty_dict.get(key, False)
                    self.__storage_cache.set_cached_value(object, key, value, dirty)
            for object_id, (object, key_list) in iter(cache_remove_copy.items()):
                for key in key_list:
                    self.__storage_cache.remove_cached_value(object, key)

    # update the value in the cache. usually updating a value in the cache
    # means it will no longer be dirty.
    def set_cached_value(self, object, key, value, dirty=False):
        # if transaction count is 0, cache directly
        if self.__storage_cache and not self.__cache_delayed:
            self.__storage_cache.set_cached_value(object, key, value, dirty)
        # otherwise, store it temporarily until transaction is finished
        else:
            with self.__cache_mutex:
                _, object_dict = self.__cache.setdefault(id(object), (object, dict()))
                _, object_list = self.__cache_remove.get(id(object), (object, list()))
                _, object_dirty_dict = self.__cache_dirty.setdefault(id(object), (object, dict()))
                object_dict[key] = value
                object_dirty_dict[key] = dirty
                if key in object_list:
                    object_list.remove(key)

    # grab the last cached value, if any, from the cache.
    def get_cached_value(self, object, key, default_value=None):
        # first check temporary cache.
        with self.__cache_mutex:
            _, object_dict = self.__cache.get(id(object), (object, dict()))
            if key in object_dict:
                return object_dict.get(key)
        # not there, go to cache db
        if self.__storage_cache and not self.__cache_delayed:
            return self.__storage_cache.get_cached_value(object, key, default_value)
        return default_value

    # removing values from the cache happens immediately under a transaction.
    # this is an area of improvement if it becomes a bottleneck.
    def remove_cached_value(self, object, key):
        # remove it from the cache db.
        if self.__storage_cache and not self.__cache_delayed:
            self.__storage_cache.remove_cached_value(object, key)
        # if its in the temporary cache, remove it
        with self.__cache_mutex:
            _, object_dict = self.__cache.get(id(object), (object, dict()))
            _, object_list = self.__cache_remove.setdefault(id(object), (object, list()))
            _, object_dirty_dict = self.__cache_dirty.get(id(object), (object, dict()))
            if key in object_dict:
                del object_dict[key]
            if key in object_dirty_dict:
                del object_dirty_dict[key]
            if key not in object_list:
                object_list.append(key)

    # determines whether the item in the cache is dirty.
    def is_cached_value_dirty(self, object, key):
        # check the temporary cache first
        with self.__cache_mutex:
            _, object_dirty_dict = self.__cache_dirty.get(id(object), (object, dict()))
            if key in object_dirty_dict:
                return object_dirty_dict[key]
        # not there, go to the db cache
        if self.__storage_cache and not self.__cache_delayed:
            return self.__storage_cache.is_cached_value_dirty(object, key)
        return True

    # set whether the cache value is dirty.
    def set_cached_value_dirty(self, object, key, dirty=True):
        # go directory to the db cache if not under a transaction
        if self.__storage_cache and not self.__cache_delayed:
            self.__storage_cache.set_cached_value_dirty(object, key, dirty)
        # otherwise mark it in the temporary cache
        else:
            with self.__cache_mutex:
                _, object_dirty_dict = self.__cache_dirty.setdefault(id(object), (object, dict()))
                object_dirty_dict[key] = dirty


class Cacheable(object):

    def __init__(self):
        super(Cacheable, self).__init__()
        self.__storage_cache = None
        self.__cache = dict()
        self.__cache_remove = list()
        self.__cache_dirty = dict()
        self.__cache_mutex = threading.RLock()
        self.__cache_delayed = False

    def get_storage_cache(self):
        return self.__storage_cache
    def set_storage_cache(self, storage_cache):
        self.__storage_cache = storage_cache
        self.storage_cache_changed(storage_cache)
        self.spill_cache()
    storage_cache = property(get_storage_cache, set_storage_cache)

    def storage_cache_changed(self, storage_cache):
        pass

    # the cache system stores values that are expensive to calculate for quick retrieval.
    # an item can be marked dirty in the cache so that callers can determine whether that
    # value needs to be recalculated. marking a value as dirty doesn't affect the current
    # value in the cache. callers can still retrieve the latest value for an item in the
    # cache even when it is marked dirty. this way the cache is used to retrieve the best
    # available data without doing additional calculations.

    # move local cache items into permanent cache when transaction is finished.
    def spill_cache(self):
        with self.__cache_mutex:
            cache_copy = copy.copy(self.__cache)
            cache_dirty_copy = copy.copy(self.__cache_dirty)
            cache_remove = copy.copy(self.__cache_remove)
            self.__cache.clear()
            self.__cache_remove = list()
            self.__cache_dirty.clear()
        if self.storage_cache:
            for key, value in iter(cache_copy.items()):
                self.storage_cache.set_cached_value(self, key, value, cache_dirty_copy.get(key, False))
            for key in cache_remove:
                self.storage_cache.remove_cached_value(self, key)

    # update the value in the cache. usually updating a value in the cache
    # means it will no longer be dirty.
    def set_cached_value(self, key, value, dirty=False):
        # if transaction count is 0, cache directly
        if self.storage_cache and not self.__cache_delayed:
            self.storage_cache.set_cached_value(self, key, value, dirty)
        # otherwise, store it temporarily until transaction is finished
        else:
            with self.__cache_mutex:
                self.__cache[key] = value
                self.__cache_dirty[key] = dirty
                if key in self.__cache_remove:
                    self.__cache_remove.remove(key)

    # grab the last cached value, if any, from the cache.
    def get_cached_value(self, key, default_value=None):
        # first check temporary cache.
        with self.__cache_mutex:
            if key in self.__cache:
                return self.__cache.get(key)
        # not there, go to cache db
        if self.storage_cache:
            return self.storage_cache.get_cached_value(self, key, default_value)
        return default_value

    # removing values from the cache happens immediately under a transaction.
    # this is an area of improvement if it becomes a bottleneck.
    def remove_cached_value(self, key):
        # remove it from the cache db.
        if self.storage_cache and not self.__cache_delayed:
            self.storage_cache.remove_cached_value(self, key)
        # if its in the temporary cache, remove it
        with self.__cache_mutex:
            if key in self.__cache:
                del self.__cache[key]
            if key in self.__cache_dirty:
                del self.__cache_dirty[key]
            if key not in self.__cache_remove:
                self.__cache_remove.append(key)

    # determines whether the item in the cache is dirty.
    def is_cached_value_dirty(self, key):
        # check the temporary cache first
        with self.__cache_mutex:
            if key in self.__cache_dirty:
                return self.__cache_dirty[key]
        # not there, go to the db cache
        if self.storage_cache:
            return self.storage_cache.is_cached_value_dirty(self, key)
        return True

    # set whether the cache value is dirty.
    def set_cached_value_dirty(self, key, dirty=True):
        # go directory to the db cache if not under a transaction
        if self.storage_cache and not self.__cache_delayed:
            self.storage_cache.set_cached_value_dirty(self, key, dirty)
        # otherwise mark it in the temporary cache
        else:
            with self.__cache_mutex:
                self.__cache_dirty[key] = dirty


#
# StorageBase supports observers and listeners.
#
# Observers can watch all serializable changes to the object by
# adding themselves as an observer and then overriding one or more
# of the following methods:
#   property_changed(object, key, value)
#   item_set(object, key, value)
#   item_cleared(object, key)
#   data_set(object, key, data)
#   item_inserted(object, key, value, before_index)
#   item_removed(object, key, value, index)
#
# Listeners listen to any notifications broadcast. They
# take the form of specific method calls on the listeners.
#
# Connections are automatically controlled listeners. They
# will be removed when the reference count goes to zero.
#

class StorageBase(Observable.Observable, Observable.Broadcaster, Cacheable):

    def __init__(self):
        super(StorageBase, self).__init__()
        self.__datastore = None
        self.storage_properties = []
        self.storage_relationships = []
        self.storage_items = []
        self.storage_type = None
        self.__reverse_aliases = dict()
        self.__weak_parents = []
        self.__uuid = uuid.uuid4()

    # uuid property. read only.
    def __get_uuid(self):
        return self.__uuid
    uuid = property(__get_uuid)
    # set is used by document controller
    def _set_uuid(self, uuid):
        self.__uuid = uuid

    # Add a parent.
    def add_parent(self, parent):
        assert parent is not None
        self.__weak_parents.append(weakref.ref(parent))

    # Remove a parent.
    def remove_parent(self, parent):
        assert parent is not None
        self.__weak_parents.remove(weakref.ref(parent))

    # Return a copy of parents array
    def get_weak_parents(self):
        return self.__weak_parents  # TODO: Return a copy
    def __get_parents(self):
        return [weak_parent() for weak_parent in self.__weak_parents]
    parents = property(__get_parents)

    # map a property to a storage key
    def register_key_alias(self, key, alias):
        self.__reverse_aliases[key] = alias

    # Send a message to the parents
    def notify_parents(self, fn, *args, **keywords):
        for parent in self.parents:
            if hasattr(parent, fn):
                getattr(parent, fn)(*args, **keywords)

    def __get_datastore(self):
        return self.__datastore
    def __set_datastore(self, datastore):
        self.__datastore = datastore
        for item_key in self.storage_items:
            item = self.get_storage_item(item_key)
            if item:
                item.datastore = datastore
        for relationship_key in self.storage_relationships:
            count = self.get_storage_relationship_count(relationship_key)
            for index in range(count):
                item = self.get_storage_relationship_item(relationship_key, index)
                item.datastore = datastore
    datastore = property(__get_datastore, __set_datastore)

    def set_storage_cache(self, storage_cache):
        for item_key in self.storage_items:
            item = self.get_storage_item(item_key)
            if item:
                item.storage_cache = storage_cache
        for relationship_key in self.storage_relationships:
            count = self.get_storage_relationship_count(relationship_key)
            for index in range(count):
                item = self.get_storage_relationship_item(relationship_key, index)
                item.storage_cache = storage_cache
        super(StorageBase, self).set_storage_cache(storage_cache)

    def get_storage_property(self, key):
        if hasattr(self, key):
            return getattr(self, key)
        if hasattr(self, "get_" + key):
            return getattr(self, "get_" + key)()
        if hasattr(self, "_get_" + key):
            return getattr(self, "_get_" + key)()
        logging.debug("get_storage_property: %s missing %s", self, key)
        raise NotImplementedError()

    def get_storage_item(self, key):
        if hasattr(self, key):
            return getattr(self, key)
        if hasattr(self, "get_" + key):
            return getattr(self, "get_" + key)()
        if hasattr(self, "_get_" + key):
            return getattr(self, "_get_" + key)()
        logging.debug("get_storage_item: %s missing %s", self, key)
        raise NotImplementedError()

    def get_storage_relationship_count(self, key):
        relationship = self.get_storage_relationship(key)
        if relationship is not None:
            return len(relationship)
        logging.debug("get_storage_relationship_count: %s missing %s", self, key)
        raise NotImplementedError()

    def get_storage_relationship_item(self, key, index):
        relationship = self.get_storage_relationship(key)
        if relationship is not None:
            return relationship[index]
        logging.debug("get_storage_relationship_item: %s missing %s[%d]", self, key, index)
        raise NotImplementedError()

    def get_storage_relationship(self, key):
        if hasattr(self, key):
            return getattr(self, key)
        if hasattr(self, "get_" + key):
            return getattr(self, "get_" + key)()
        if hasattr(self, "_get_" + key):
            return getattr(self, "_get_" + key)()
        return None

    # implement observer/notification mechanism

    def notify_set_property(self, key, value):
        if key in self.storage_properties:
            if self.datastore:
                resolved_key = self.__reverse_aliases.get(key, key)
                self.datastore.set_property(self, resolved_key, value)
        super(StorageBase, self).notify_set_property(key, value)

    def notify_set_item(self, key, item):
        if key in self.storage_items:
            assert item is not None
            if self.datastore:
                item.datastore = self.datastore
                resolved_key = self.__reverse_aliases.get(key, key)
                self.datastore.set_item(self, resolved_key, item)
            if self.storage_cache:
                item.storage_cache = self.storage_cache
            if item:
                item.add_parent(self)
        super(StorageBase, self).notify_set_item(key, item)

    def notify_clear_item(self, key):
        if key in self.storage_items:
            item = self.get_storage_item(key)
            if item:
                if self.datastore:
                    resolved_key = self.__reverse_aliases.get(key, key)
                    self.datastore.clear_item(self, resolved_key)
                    item.datastore = None
                if self.storage_cache:
                    item.storage_cache = None
                item.remove_parent(self)
        super(StorageBase, self).notify_clear_item(key)

    def notify_insert_item(self, key, value, before_index):
        if key in self.storage_relationships:
            assert value is not None
            if self.datastore:
                value.datastore = self.datastore
                resolved_key = self.__reverse_aliases.get(key, key)
                self.datastore.insert_item(self, resolved_key, value, before_index)
            if self.storage_cache:
                value.storage_cache = self.storage_cache
            value.add_parent(self)
        super(StorageBase, self).notify_insert_item(key, value, before_index)

    def notify_remove_item(self, key, value, index):
        if key in self.storage_relationships:
            assert value is not None
            if self.datastore:
                resolved_key = self.__reverse_aliases.get(key, key)
                self.datastore.remove_item(self, resolved_key, index)
                value.datastore = None
            if self.storage_cache:
                value.storage_cache = None
            value.remove_parent(self)
        super(StorageBase, self).notify_remove_item(key, value, index)

    def write(self):
        assert self.datastore is not None
        for property_key in self.storage_properties:
            value = self.get_storage_property(property_key)
            if value:
                resolved_property_key = self.__reverse_aliases.get(property_key, property_key)
                self.datastore.set_property(self, property_key, value)
        for item_key in self.storage_items:
            item = self.get_storage_item(item_key)
            if item:
                # TODO: are these redundant?
                item.datastore = self.datastore
                item.storage_cache = self.storage_cache
                resolved_item_key = self.__reverse_aliases.get(item_key, item_key)
                self.datastore.set_item(self, resolved_item_key, item)
        for relationship_key in self.storage_relationships:
            count = self.get_storage_relationship_count(relationship_key)
            for index in range(count):
                item = self.get_storage_relationship_item(relationship_key, index)
                # TODO: are these redundant?
                item.datastore = self.datastore
                item.storage_cache = self.storage_cache
                resolved_relationship_key = self.__reverse_aliases.get(relationship_key, relationship_key)
                self.datastore.insert_item(self, resolved_relationship_key, item, index)
        if self.datastore:
            self.datastore.set_type(self, self.storage_type)

    # only used for testing
    def rewrite_object(self):
        assert self.datastore is not None
        self.datastore.erase_object(self)
        self.write()



def db_make_directory_if_needed(directory_path):
    if os.path.exists(directory_path):
        if not os.path.isdir(directory_path):
            raise OSError("Path is not a directory:", directory_path)
    else:
        os.makedirs(directory_path)


class DictStorageCache(object):
    def __init__(self):
        self.__cache = dict()
        self.__cache_dirty = dict()

    def close(self):
        pass

    @property
    def cache(self):
        return self.__cache

    def set_cached_value(self, object, key, value, dirty=False):
        cache = self.__cache.setdefault(object.uuid, dict())
        cache_dirty = self.__cache_dirty.setdefault(object.uuid, dict())
        cache[key] = value
        cache_dirty[key] = False

    def get_cached_value(self, object, key, default_value=None):
        cache = self.__cache.setdefault(object.uuid, dict())
        return cache.get(key, default_value)

    def remove_cached_value(self, object, key):
        cache = self.__cache.setdefault(object.uuid, dict())
        cache_dirty = self.__cache_dirty.setdefault(object.uuid, dict())
        if key in cache:
            del cache[key]
        if key in cache_dirty:
            del cache_dirty[key]

    def is_cached_value_dirty(self, object, key):
        cache_dirty = self.__cache_dirty.setdefault(object.uuid, dict())
        return cache_dirty[key] if key in cache_dirty else True

    def set_cached_value_dirty(self, object, key, dirty=True):
        cache_dirty = self.__cache_dirty.setdefault(object.uuid, dict())
        cache_dirty[key] = dirty


class DbStorageCache(object):
    def __init__(self, cache_filename):
        self.__queue = queue.Queue()
        self.__queue_lock = threading.RLock()
        self.__started_event = threading.Event()
        self.__thread = threading.Thread(target=self.__run, args=[cache_filename])
        self.__thread.daemon = True
        self.__thread.start()
        self.__started_event.wait()

    def close(self):
        with self.__queue_lock:
            assert self.__queue is not None
            self.__queue.put((None, None, None, None))
            self.__queue.join()
            self.__queue = None

    def __run(self, cache_filename):
        self.conn = sqlite3.connect(cache_filename)
        self.conn.execute("PRAGMA synchronous = OFF")
        self.__create()
        self.__started_event.set()
        while True:
            action = self.__queue.get()
            item, result, event, action_name = action
            #logging.debug("item %s  result %s  event %s  action %s", item, result, event, action_name)
            if item:
                try:
                    #logging.debug("EXECUTE %s", action_name)
                    start = time.time()
                    if result is not None:
                        result.append(item())
                    else:
                        item()
                    elapsed = time.time() - start
                    #logging.debug("ELAPSED %s", elapsed)
                except Exception as e:
                    import traceback
                    logging.debug("DB Error: %s", e)
                    traceback.print_exc()
                    traceback.print_stack()
                finally:
                    #logging.debug("FINISH")
                    if event:
                        event.set()
            self.__queue.task_done()
            if not item:
                break
        self.conn.close()
        self.conn = None

    def __create(self):
        with self.conn:
            self.execute("CREATE TABLE IF NOT EXISTS cache(uuid STRING, key STRING, value BLOB, dirty INTEGER, PRIMARY KEY(uuid, key))")

    def execute(self, stmt, args=None, log=False):
        if args:
            result = self.conn.execute(stmt, args)
            if log:
                logging.debug("%s [%s]", stmt, args)
            return result
        else:
            self.conn.execute(stmt)
            if log:
                logging.debug("%s", stmt)
            return None

    def __set_cached_value(self, object, key, value, dirty=False):
        with self.conn:
            self.execute("INSERT OR REPLACE INTO cache (uuid, key, value, dirty) VALUES (?, ?, ?, ?)", (str(object.uuid), key, sqlite3.Binary(pickle.dumps(value, 0)), 1 if dirty else 0))

    def __get_cached_value(self, object, key, default_value=None):
        last_result = self.execute("SELECT value FROM cache WHERE uuid=? AND key=?", (str(object.uuid), key))
        value_row = last_result.fetchone()
        if value_row is not None:
            if sys.version < '3':
                result = pickle.loads(bytes(bytearray(value_row[0])))
            else:
                result = pickle.loads(value_row[0], encoding='latin1')
            return result
        else:
            return default_value

    def __remove_cached_value(self, object, key):
        with self.conn:
            self.execute("DELETE FROM cache WHERE uuid=? AND key=?", (str(object.uuid), key))

    def __is_cached_value_dirty(self, object, key):
        last_result = self.execute("SELECT dirty FROM cache WHERE uuid=? AND key=?", (str(object.uuid), key))
        value_row = last_result.fetchone()
        if value_row is not None:
            return value_row[0] != 0
        else:
            return True

    def __set_cached_value_dirty(self, object, key, dirty=True):
        with self.conn:
            self.execute("UPDATE cache SET dirty=? WHERE uuid=? AND key=?", (1 if dirty else 0, str(object.uuid), key))

    def set_cached_value(self, object, key, value, dirty=False):
        event = threading.Event()
        with self.__queue_lock:
            queue = self.__queue
        if queue:
            queue.put((functools.partial(self.__set_cached_value, object, key, value, dirty), None, event, "set_cached_value"))
        #event.wait()

    def get_cached_value(self, object, key, default_value=None):
        event = threading.Event()
        result = list()
        with self.__queue_lock:
            queue = self.__queue
        if queue:
            queue.put((functools.partial(self.__get_cached_value, object, key, default_value), result, event, "get_cached_value"))
            event.wait()
        return result[0] if len(result) > 0 else None

    def remove_cached_value(self, object, key):
        event = threading.Event()
        with self.__queue_lock:
            queue = self.__queue
        if queue:
            queue.put((functools.partial(self.__remove_cached_value, object, key), None, event, "remove_cached_value"))
        #event.wait()

    def is_cached_value_dirty(self, object, key):
        event = threading.Event()
        result = list()
        with self.__queue_lock:
            queue = self.__queue
        if queue:
            queue.put((functools.partial(self.__is_cached_value_dirty, object, key), result, event, "is_cached_value_dirty"))
            event.wait()
        return result[0]

    def set_cached_value_dirty(self, object, key, dirty=True):
        event = threading.Event()
        with self.__queue_lock:
            queue = self.__queue
        if queue:
            queue.put((functools.partial(self.__set_cached_value_dirty, object, key, dirty), None, event, "set_cached_value_dirty"))
        #event.wait()
