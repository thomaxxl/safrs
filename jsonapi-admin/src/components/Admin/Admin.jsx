import React from 'react';
import * as ObjectAction from 'action/ObjectAction'
import * as SpinnerAction from 'action/SpinnerAction'
import { connect } from 'react-redux'
import { bindActionCreators } from 'redux'
import * as analyzejson from './analyzejson'
import toastr from 'toastr';
import { RingLoader } from 'react-spinners';
import { 
  Grid, 
  Segment, 
  Header,
  List,
  Tab
} from 'semantic-ui-react'

import Confactions from './confactions'
import Otheroption from './otheroption'
import Attributes from './attributes'
import Relationship from './relationship'


import 'semantic-ui-css/semantic.min.css'
import 'bootstrap/dist/css/bootstrap.min.css'
import './Admin.css'

import {
  InputGroup,
  InputGroupAddon,
  Input,
  Container, 
  Row,
  Button,
} from 'reactstrap';

const toasterPosition =  {positionClass: "toast-top-center"}

let styles = {
  marginTop: "30px"
}

let btnstyle = {
  backgroundColor: "#343a40"
}

var stylefloat1 = {
  // float: "right",
  marginTop: "10px",
  width: "100%"
}

var whitestyle = {
  color: "white"
}

let backstyle = {
  backgroundColor: "#e5e5e5"
}

var styleheight1 = {
  overflowY: "scroll",
  maxHeight: "600px",
  height:"600px"
}

var styleheight2 = {
  height:"210px",
  overflowY: "scroll",
  maxHeight:"210px",
}

var styleheight3 = {
  height:"330px",
  overflowY: "scroll",
  maxHeight:"330px",
}
class Admin extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
      error:[],
      discover: 0,
      url: '',
      selected: 0,
      collections: ['Book', 'School', 'Color', 'Love'],
      otheroption: ['path', 'API', 'API_TYPE', 'menu', 'Title', 'request_args']
    }
    this.handle_json_url = this.handle_json_url.bind(this)
    this.handleClick = this.handleClick.bind(this)
    this.handleselect = this.handleselect.bind(this)
    this.handlegenerate = this.handlegenerate.bind(this)
    this.handleRemove = this.handleRemove.bind(this)
    this.handleDiscoverClick = this.handleDiscoverClick.bind(this)
  }  

  handle_json_url(e) {
    e.preventDefault()
    this.setState({ url: e.target.value})
  }

  handleselect(index) {
    this.setState({
      selected: index
    })
  }

  componentDidMount() {
    this.setState({url: localStorage.getItem('json_url') === null? 'http://thomaxxl.pythonanywhere.com/api/swagger.json': localStorage.getItem('json_url')})
  }

  handleClick(e) {
    e.preventDefault()
    this.props.spinnerAction.getSpinnerStart()
    localStorage.setItem('json_url', this.state.url)
    ObjectAction.getJsondata(this.state.url)
    .then((data) => {
      this.props.spinnerAction.getSpinnerEnd()
      if (data.status === undefined) {
        toastr.error('Please input valid url', '', toasterPosition)
        this.setState({discover: 0})
      } else {
        this.props.analyze.analyzejson(data)
        this.setState({discover: 1})
      }
    })
      // toastr.error('Please input valid url', '', toasterPosition)
    .then(()=> {

    toastr.info('Discovering Relationships')
    this.props.spinnerAction.getSpinnerStart()
    ObjectAction.getJsondata(this.state.url)
    .then((data) => {
      // this.props.spinnerAction.getSpinnerEnd()
      if (data.status === undefined) {
      } else {
        toastr.info('Now Generate Config !')
        this.props.analyze.analyzejsonrelationship(data)
        //this.handlegenerate()
      }
    })
    .catch((error) => {
      console.log(error)
      toastr.error('Please input valid url', '', toasterPosition)
    }) } )
  }

  handleDiscoverClick(e) {
    e.preventDefault()
    this.props.spinnerAction.getSpinnerStart()
    ObjectAction.getJsondata(this.state.url)
    .then((data) => {
      // this.props.spinnerAction.getSpinnerEnd()
      if (data.status === undefined) {
      } else {
        this.props.analyze.analyzejsonrelationship(data)
      }
    })
    .catch((error) => {
      // toastr.error('Please input valid url', '', toasterPosition)
    })
  }

  handlegenerate() {
    let check = 0
    let errors = []
    Object.keys(this.props.json).map(function(key, index) {
      this.props.json[key]['relationship'].map((rkey, rindex) => {
        if (this.props.json[key]['relationship'][rkey]['relationship'] === '') { 
          check += 1
          errors.push({
            collection: key,
            relationship: rkey
          })
        }
        return true
      })
      return true
    }, this)
    if (check) {
      toastr.error('Please select relationships option', '', toasterPosition)
      console.log(['error', errors])
      this.setState({
        error: errors
      })
      return
    }
    Object.keys(this.props.json).map(function(key, index) {
      let column = []
      this.props.json[key]['attributes'].map((akey, aindex) => {
        column.push(this.props.json[key]['attributes'][akey])
        return true
      })
      delete this.props.json[key].attributes
      this.props.json[key]['relationship'].map((rkey, rindex) => {
        delete this.props.json[key]['relationship'][rkey].attributesId
        delete this.props.json[key]['relationship'][rkey].collectionId
        column.push(this.props.json[key]['relationship'][rkey])
        return true
      })
      delete this.props.json[key].relationship
      delete this.props.json[key].attributes1
      this.props.json[key]['column'] = column
      return true
    }, this)
    localStorage.setItem('json', JSON.stringify(this.props.json))
    this.props.history.push('/')
    window.location.reload()
  }

  handleRemove(){
    let check = 0
    let errors = []

    console.log(this.props.json)
    console.log(this.state)
    Object.keys(this.props.json).map(function(key, index) {
      if(index == this.state.selected){
        delete this.props.json[key]
        return
      }
    }, this)
  }

  render() {
    let collections = []
    
    const panes = [
      { menuItem: 'Admin', render: () => <Tab.Pane>Admin</Tab.Pane> },
      { menuItem: 'JSON', render: () => <Tab.Pane>JSON</Tab.Pane> }
    ]


    if(Object.keys(this.props.json).length !== 0){
      Object.keys(this.props.json).map(function(key, index) {
        collections.push(key)
        return true
      })
    }
    if(this.props.spin){
      return (
        <RingLoader
          color={'#123abc'} 
          loading={this.props.spin} 
        />
      )
    }
    return (
      <Container>
        <Row style={styles}>
          <InputGroup>
            <InputGroupAddon addonType="prepend">OAS(Swagger) JSON</InputGroupAddon>
            <Input 
              onChange={this.handle_json_url}
              value={this.state.url }
            />
            <Button color="secondary" onClick={this.handleClick}>Analyze OAS</Button>
            {
              this.state.discover === 1?
                <Button style={btnstyle} onClick={this.handleDiscoverClick}>Discover relationship</Button>
                :<div></div>
            }
          </InputGroup>
        </Row>
        <Tab panes={panes} />

        <Grid>
          <Grid.Row className="rowstyle">
            <Grid.Column width={4}>
              <Segment style={styleheight1}>
                <div>
                  <Header as='h3'>Collections</Header>
                  <List divided selection>
                  {
                    collections.map((Item, index) => {
                      let cons = {}
                      if (index === this.state.selected) cons = backstyle
                      return(
                        <List.Item key={index} value='index' style={cons} onClick={() => this.handleselect(index)}>
                          <List.Content>{Item}</List.Content>
                        </List.Item>
                      )
                    })
                  }
                  <Button onClick={this.handlegenerate}disabled={Object.keys(this.props.json).length !== 0?false:true} style={stylefloat1}>Generate config</Button>
                  <Button onClick={this.handleRemove}disabled={Object.keys(this.props.json).length !== 0?false:true} style={stylefloat1}>Remove Item</Button>
                  </List>
                </div>
                <Segment inverted color='orange'>
                  <List divided selection>
                  {
                    this.state.error.map((key, index) => {
                      return(
                        <List.Item key={index}>
                          <List.Content style={whitestyle}>{key.collection} --> {key.relationship}</List.Content>
                        </List.Item>
                      )
                    })
                  }
                  </List>
                </Segment>
              </Segment>
              
            </Grid.Column>
            <Grid.Column width={8}>
              <Segment style={styleheight1}>
                <Grid>
                  <Grid.Column width={16}>
                    <Segment style={styleheight2}>
                      <Attributes index={this.state.selected}/>
                    </Segment>
                  </Grid.Column>
                  <Grid.Column width={16}>
                    <Segment style={styleheight3}>
                      <Relationship index={this.state.selected}/>
                    </Segment>
                  </Grid.Column>
                </Grid>
              </Segment>
            </Grid.Column>
            <Grid.Column width={4}>
              <Segment style={styleheight1}>
                <Grid>
                  <Grid.Column width={16}>
                    <Segment style={styleheight2}>
                      <Confactions index={this.state.selected}/>
                    </Segment>
                  </Grid.Column>
                  <Grid.Column width={16}>
                    <Segment style={styleheight3}>
                      <Otheroption index={this.state.selected}/>
                    </Segment>
                  </Grid.Column>
                </Grid>
              </Segment>
            </Grid.Column>
          </Grid.Row>
        </Grid>
      </Container>
    );
  }
};

const mapStateToProps = (state) => ({
  spin: state.analyzeReducer.spinner,
  json: state.configReducer
})

const mapDispatchToProps = dispatch => ({
  action: bindActionCreators(ObjectAction, dispatch),
  spinnerAction: bindActionCreators(SpinnerAction, dispatch),
  analyze: bindActionCreators(analyzejson, dispatch)
})


export default connect(mapStateToProps, mapDispatchToProps)(Admin)
