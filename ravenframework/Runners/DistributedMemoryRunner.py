# Copyright 2017 Battelle Energy Alliance, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Created on Mar 5, 2013

@author: alfoa, cogljj, crisr, talbpw, maljdp
"""
#External Modules------------------------------------------------------------------------------------
import sys
import gc
from ..utils import importerUtils as im
## TODO: REMOVE WHEN RAY AVAILABLE FOR WINDOWOS
if im.isLibAvail("ray"):
  import ray
else:
  import inspect
#External Modules End--------------------------------------------------------------------------------

#Internal Modules------------------------------------------------------------------------------------
from ..utils import utils
from .InternalRunner import InternalRunner
#Internal Modules End--------------------------------------------------------------------------------

waitTimeOut = 1e-10 # timeout to check for job to finish

class DistributedMemoryRunner(InternalRunner):
  """
    Class for running internal objects in distributed memory fashion using
    ppserver
  """
  def __init__(self, args, functionToRun, **kwargs):
    """
      Init method
      @ In, args, list, this is a list of arguments that will be passed as
        function parameters into whatever method is stored in functionToRun.
        e.g., functionToRun(*args)
      @ In, functionToRun, method or function, function that needs to be run
      @ In, kwargs, dict, additional arguments to base class
      @ Out, None
    """
    ## First, allow the base class to handle the commonalities
    ##   We keep the command here, in order to have the hook for running exec
    ##   code into internal models
    if not im.isLibAvail("ray"):
      self.__ppserver, args = args[0], args[1:]
    super().__init__(args, functionToRun, **kwargs)

  def isDone(self):
    """
      Method to check if the calculation associated with this Runner is finished
      @ In, None
      @ Out, finished, bool, is it finished?
    """
    ## If the process has not been started yet, then return False
    if not self.started:
      return False

    if self.thread is None:
      return True
    else:
      if im.isLibAvail("ray"):
        try:
          ray.get(self.thread, timeout=waitTimeOut)
          return True
        except ray.exceptions.GetTimeoutError:
          return False
        except ray.exceptions.RayTaskError:
          #The code gets this undocumented error, and
          # I assume it means the task has unfixably died,
          # and so is done
          return True
        #Alternative that was tried:
        #return self.thread in ray.wait([self.thread], timeout=waitTimeOut)[0]
        #which ran slower in ray 1.9
      else:
        return self.thread.finished

  def _collectRunnerResponse(self):
    """
      Method to add the process response in the internal variable (pointer)
      self.__runReturn
      @ In, None
      @ Out, None
    """
    if not self.hasBeenAdded:
      if self.thread is not None:
        self.runReturn = ray.get(self.thread) if im.isLibAvail("ray") else self.thread()
      else:
        self.runReturn = None
      self.hasBeenAdded = True

  def start(self):
    """
      Method to start the job associated to this Runner
      @ In, None
      @ Out, None
    """
    try:
      if im.isLibAvail("ray"):
        self.thread = self.functionToRun(*self.args)
      else:
        self.thread = self.__ppserver.submit(self.functionToRun, args=self.args, depfuncs=(),
                                             modules = tuple([self.functionToRun.__module__]+list(set(utils.returnImportModuleString(inspect.getmodule(self.functionToRun),True)))))
      self.trackTime('runner_started')
      self.started = True
      gc.collect()
      return

    except Exception as ae:
      #Uncomment if you need the traceback
      self.exceptionTrace = sys.exc_info()
      #exc_type, exc_value, exc_traceback = sys.exc_info()
      #import traceback
      #traceback.print_exception(exc_type, exc_value, exc_traceback)
      self.raiseAWarning(self.__class__.__name__ + " job "+self.identifier+" failed with error:"+ str(ae) +" !",'ExceptedError')
      self.returnCode = -1

  def kill(self):
    """
      Method to kill the job associated to this Runner
      @ In, None
      @ Out, None
    """
    del self.thread
    self.thread = None
    self.returnCode = -1
    self.trackTime('runner_killed')
