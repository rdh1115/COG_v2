from typing import List, Dict, Any

import numpy as np
import task_generator as tg
import stim_generator as sg
import frame_info as fi
from combo_task_info import ComboTaskInfo

def get_target_value(t):
    # Convert target t to string and convert True/False target values
    # to lower case strings for consistency with other uses of true/false
    # in vocabularies.
    t = t.value if hasattr(t, 'value') else str(t)
    if t is True or t == 'True':
        return 'true'
    if t is False or t == 'False':
        return 'false'
    return t


class TaskInfoConvert(object):
    """Base class for frame_info"""
    # task_info: List[Dict[str, Any]]

    def __init__(self, task_example=None, task=None, objset=None):
        " task examples include family, epochs, question, objects, answers"
        " always init frame_info with a single task generated by one tree "
        " combining with a second task should be implemented incrementally"

        self.objset = objset
        if task is None or objset is None:
            if task_example is None:
                raise ValueError("no tasks is provided")
            # initiate frame_info by given task_example
            else:
                self.task_info = [{}]
                self.task_info[0]["task_family"] = task_example["family"]
                self.task_info[0]["is_intact"] = False
                self.task_info[0]["question"] = task_example["question"]
                self.task_info[0]["answers"] = task_example["answers"]

                self._n_epochs = task_example["epochs"]
                self.task_info[0]["task_len"] = self._n_epochs

                cur_task = self.task_info[0]
                self.frame_info = fi.FrameInfo(self._n_epochs,
                                               {0},
                                               cur_task['question'],
                                               cur_task['answers'],
                                               self.objset
                                               )
        else:
            if task.n_frames != objset.n_epoch:
                raise ValueError('Task epoch does not equal objset epoch')

            assert isinstance(task, tg.TemporalTask)

            self.task_info = [{}]
            self.task_info[0]['shareable'] = task.shareable
            self.task_info[0]["task_family"] = task.__class__.__name__
            self.task_info[0]["question"] = str(task)
            self.task_info[0]["answers"] = [get_target_value(t) for t in task.get_target(objset)]
            self.task_info[0]["task_len"] = task.n_frames
            self._n_epochs = self.task_info[0]["task_len"]

            cur_task = self.task_info[0]
            self.frame_info = fi.FrameInfo(self._n_epochs,
                                           {0},
                                           cur_task['shareable'],
                                           cur_task['question'],
                                           cur_task['answers'],
                                           objset
                                           )

    def __len__(self):
        # return number of tasks involved
        return len(self.task_info)

    @property
    def n_epochs(self):
        return len(self.frame_info)

    def index_conv(self, frame_idx, task_idx):
        # return epoch index for given frame index and task index
        return self.frame_info[frame_idx]["relative_task_epoch_idx"][task_idx][0]

    def merge(self, new_task_info = ComboTaskInfo(), reuse=None):
        '''

        :param new_task_info: TaskInfoConvert object
        :return: None if no change, and the new task if merge needed change
        '''
        # TODO(mbai): change task instruction here
        # TODO: location conflict, feature (shape, color) conflict

        assert isinstance(new_task_info, TaskInfoConvert)
        if len(new_task_info.task_info) > 1:
            raise NotImplementedError('Currently cannot support adding new composite tasks')

        if reuse is None:
            reuse = 0.5

        # correct task index in new_task_info
        next_task_idx = len(self.task_info)
        for frame in new_task_info.frame_info:
            frame.relative_tasks = [next_task_idx + i for i, task in enumerate(frame.relative_tasks)]
            for i, task in enumerate(frame.relative_tasks):
                frame.relative_task_epoch_idx[next_task_idx + i] = frame.relative_task_epoch_idx[task].pop()
                task = next_task_idx + i

        start = self.frame_info.get_start_frame()

        if start == -1:
            # queue
            extra_f = len(new_task_info.frame_info)
        else:
            extra_f = new_task_info.n_epochs - self.n_epochs - start

        for i in range(extra_f):
            self.add_new_frame({next_task_idx}, new_task_info)

        curr_abs_idx = start
        for i, curr_frame in enumerate(self.frame_info[start:]):
            ### todo: define empty; what is curr_frame.objs?!!!!
            if curr_frame.objs is empty or new_task_info.frame_info[i].objs is empty:
                self.frame_info[i].compatible_merge(new_task_info.frame_info[i]) # always update frame descriptions
            else:
                if np.random.random() < reuse: # use previous frame info and reinit new task
                    # identify select operator associated with the new_task
                    incoming_select_op = new_task_info.task.track_op[i].update(curr_frame.objs)
                    attr_expected = dict()
                    attr_expected["sel_op_idx"] = i
                    for attr_type in incoming_select_op.inherent_attr:
                        a = incoming_select_op.getattr(attr_type)
                        if isinstance(a, Operator): pass
                        else: attr_expected[attr_type] = a
                    # attr_expected: dictionary with restrictions on current select operator
                    # update task with attr_expected
                    new_task_info.task.update(attr_expected[attr_type])
                    new_task_info.objset = new_task_info.task.generate_objset(n_epoch=new_task_info.task.n_frames, average_memory_span=new_task_info.task.avg_mem_span)
                    new_task_info.example["question"] = str(new_task_info.task)
                    new_task_info.example["objects"] = [o.dump() for o in new_task_info.objset]
                    targets = new_task_info.task.get_target(objset)
                    new_task_info.example["answers"] = [get_target_value(t) for t in targets]
                    #### xlei: do we still need compatible merge since the new task will use the information from the previous one?
                    #### xlei: yes! we need to update all the index and task descriptions
                    #### xlei: or maybe we have done it already?
                else:
                    ## xlei: compatible merge use add function to add objects to the previous frame
                    ## xlei: don't forget to update frameinfo and objset(this one should have been updated in the add process)
                    ## xlei: so only merge frameinfo
                    self.compatible_merge(new_task_info.frame_info[i])




            curr_abs_idx += 1
        # reuse visual stimuli with probability reuse

        ########## delete below
        # if np.random.random() < reuse:
        #     # reuse past info, and resolve conflict
        #     for i, curr_frame in enumerate(self.frame_info[start:]):
        #         if new_task_info.frame_info[i].objs != curr_frame.objs: # subset
        #             # identify which select operator for this frame: add self.track_op in the GoShape task
        #             ### todo: move it to the Task Class as a general attribute?
        #             ### todo: what is the task here? I need to get access to the operator so suppose we have the initialized task
        #             # current select operator is new_task_info.task.track_op[i]
        #             # update the associate select operator with curr_frame.objs information, if multiple, choose one
        #             new_task_info.task.track_op[i].update(curr_frame.objs)
        #     ####### after this loop, new task with updated info should be compatible with the previous one
        #
        #     ### todo: self.compatible_merge()
        #     return self.compatible_merge(new_task_info, add_stim = False) # compatible merge means merge two task without adding new stims
        #
        # # create new frames and merge
        # else:
        #     # find the first consecutively shareable frame
        #     # add more frames or change lastk? add more frames for now
        #     if start == -1:
        #         # queue
        #         extra_f = len(new_task_info.frame_info)
        #     else:
        #         extra_f = new_task_info.n_epochs - self.n_epochs - start
        #
        #     for i in range(extra_f):
        #         self.add_new_frame({next_task_idx}, new_task_info)
        #
        #     for old, new in zip(self.frame_info[start, len(self.frame_info)], new_task_info.frame_info):
        #         old.merge(new)

        self.task_info.append(new_task_info.task_info[0])
        return

    def add_new_frame(self, relative_tasks, new_task_info):
        # add new empty frames
        self.frame_info.frame_list.append(self.frame_info.Frame(
            len(self.frame_info),
            relative_tasks,
            new_task_info.task_info[0]['shareable']
        ))

    def inv_convert(self):
        # inverse the frameinfo to task examples
        examples = []
        for i in range(len(self)):
            examples.append[{}]
            examples[i]["family"] = self.task_info[i]["task_family"]
            examples[i]["epochs"] = self.task_info[i]["task_len"]
            examples[i]["question"] = self.task_info[i]["question"]
            examples[i]["answers"] = self.task_info[i]["answers"]
            examples[i]["is_intact"] = self.task_info[i]["is_intact"]

            inv_frame_index = []  # frame index if involved in task i
            objects_feat = []
            objects = []
            curr_obj = {}
            for j, frame in enumerate(self.frame_info):
                if i in frame["relative_tasks"]:
                    count_i = frame["relative_tasks"].index(i)
                    inv_frame_index.append(j)
                    for obj in self.frame_info[j]["objs"]:
                        for features in ["location", "shape", "color", "is_distractor"]:
                            curr_obj[features] = obj[features]

                        if curr_obj not in objects_feat:
                            curr_obj["epochs"] = [self.frame_info[j]["relative_task_epoch_idx"][count_i]]
                            objects_feat.append(curr_obj)
                            objects.append(curr_obj)
                        else:
                            obj_idx = objects_feat.index(curr_obj)
                            objects[obj_idx]["epochs"].append(self.frame_info[j]["relative_task_epoch_idx"][count_i])
                examples[i]["objects"] = objects
        return examples

    def inv_convert_objset(self):
        '''

        :return: list of objsets
        '''
        # convert frame_info to objset
        pass

    def task_update(self):
        pass
        # todo: update task upon request
